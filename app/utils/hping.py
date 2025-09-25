"""
hping3 command generation utilities
"""

from typing import List, Optional, Dict, Any
import re
import shlex
import structlog

from app.api.schemas import JobCreateRequest, TrafficType
from app.utils.validation import sanitize_payload, validate_port, validate_interface_name

logger = structlog.get_logger()


class HpingCommandBuilder:
    """Builds safe hping3 commands from job specifications"""
    
    # Allowed hping3 options for security
    ALLOWED_OPTIONS = {
        '--fast', '--faster', '--flood',
        '-V', '--verbose', '-q', '--quiet',
        '--baseport', '--destport', '--keep',
        '--rand-dest', '--rand-source'
    }
    
    # Maximum values for safety
    MAX_COUNT = 1000000
    MAX_INTERVAL = 1000000  # microseconds
    MIN_INTERVAL = 1000     # microseconds (1ms minimum)
    
    def __init__(self):
        self.logger = structlog.get_logger()
    
    def build_command(self, job_spec: JobCreateRequest, target: str) -> List[str]:
        """
        Build hping3 command arguments for a specific target
        Returns list of command arguments (no shell injection possible)
        """
        args = ["hping3"]
        
        # Traffic type specific options
        if job_spec.traffic_type == TrafficType.UDP:
            args.append("--udp")
        elif job_spec.traffic_type == TrafficType.ICMP:
            args.append("--icmp")
        elif job_spec.traffic_type == TrafficType.TCP_SYN:
            args.append("-S")  # SYN flag
        
        # Destination port
        if job_spec.dst_port and validate_port(job_spec.dst_port):
            args.extend(["-p", str(job_spec.dst_port)])
        
        # Source port
        if job_spec.src_port and job_spec.src_port > 0 and validate_port(job_spec.src_port):
            args.extend(["--baseport", str(job_spec.src_port)])
        
        # Packet size (data payload)
        if job_spec.packet_size > 0:
            args.extend(["-d", str(min(job_spec.packet_size, 65507))])
        
        # TTL
        if job_spec.ttl and 1 <= job_spec.ttl <= 255:
            args.extend(["-t", str(job_spec.ttl)])
        
        # Interface
        if job_spec.iface and validate_interface_name(job_spec.iface):
            args.extend(["-I", job_spec.iface])
        
        # Source IP spoofing (only if enabled and valid)
        if job_spec.spoof_source and job_spec.source_ip:
            args.extend(["-a", job_spec.source_ip])
        
        # Rate control (packets per second -> interval in microseconds)
        if job_spec.pps > 0:
            # Convert PPS to interval in microseconds
            interval_us = max(self.MIN_INTERVAL, min(self.MAX_INTERVAL, int(1_000_000 / job_spec.pps)))
            args.extend(["-i", f"u{interval_us}"])
        
        # Count (duration * pps) - if duration is set
        if job_spec.duration > 0:
            count = min(self.MAX_COUNT, job_spec.pps * job_spec.duration)
            args.extend(["-c", str(count)])
        
        # Custom payload
        if job_spec.payload:
            sanitized_payload = sanitize_payload(job_spec.payload)
            if sanitized_payload:
                # For hex payload, use -E flag
                if self._is_hex_string(sanitized_payload):
                    args.extend(["-E", sanitized_payload])
                else:
                    # For ASCII payload, use -e flag
                    args.extend(["-e", sanitized_payload])
        
        # Additional safe hping options
        if job_spec.hping_options:
            safe_options = self._validate_hping_options(job_spec.hping_options)
            args.extend(safe_options)
        
        # Add verbose output for parsing
        if "-V" not in args and "--verbose" not in args:
            args.append("-V")
        
        # Target (add last)
        args.append(target)
        
        self.logger.info("Generated hping3 command", 
                        target=target, 
                        traffic_type=job_spec.traffic_type,
                        args=args)
        
        return args
    
    def build_commands_for_targets(self, job_spec: JobCreateRequest) -> Dict[str, List[str]]:
        """
        Build hping3 commands for all targets in job spec
        Returns dict mapping target -> command args
        """
        commands = {}
        
        for target in job_spec.targets:
            try:
                command = self.build_command(job_spec, target)
                commands[target] = command
            except Exception as e:
                self.logger.error("Failed to build command for target", 
                                target=target, error=str(e))
                
        return commands
    
    def _validate_hping_options(self, options: List[str]) -> List[str]:
        """Validate and filter hping3 options for security"""
        safe_options = []
        
        for option in options:
            option = option.strip()
            if not option:
                continue
                
            # Check if option is in allowed list
            is_allowed = False
            for allowed in self.ALLOWED_OPTIONS:
                if option == allowed or option.startswith(allowed + '='):
                    is_allowed = True
                    break
            
            if is_allowed:
                safe_options.append(option)
            else:
                self.logger.warning("Rejected unsafe hping option", option=option)
        
        return safe_options
    
    def _is_hex_string(self, s: str) -> bool:
        """Check if string is a valid hex string"""
        try:
            int(s, 16)
            return len(s) % 2 == 0  # Must be even length for hex bytes
        except ValueError:
            return False
    
    def get_command_string(self, args: List[str]) -> str:
        """Convert command args to shell-safe string for display"""
        return ' '.join(shlex.quote(arg) for arg in args)


# Global command builder instance
command_builder = HpingCommandBuilder()


def generate_job_commands(job_spec: JobCreateRequest) -> Dict[str, Any]:
    """
    Generate hping3 commands for a job specification
    Returns dict with commands and metadata
    """
    try:
        commands = command_builder.build_commands_for_targets(job_spec)
        
        # Generate display strings
        command_strings = {
            target: command_builder.get_command_string(args)
            for target, args in commands.items()
        }
        
        return {
            "success": True,
            "commands": commands,
            "command_strings": command_strings,
            "target_count": len(commands),
            "estimated_duration": job_spec.duration if job_spec.duration > 0 else None,
            "estimated_packets": job_spec.pps * job_spec.duration if job_spec.duration > 0 else None
        }
        
    except Exception as e:
        logger.error("Failed to generate job commands", error=str(e))
        return {
            "success": False,
            "error": str(e),
            "commands": {},
            "command_strings": {}
        }


def validate_job_spec(job_spec: JobCreateRequest) -> Dict[str, Any]:
    """
    Validate job specification before command generation
    Returns validation result with errors if any
    """
    errors = []
    warnings = []
    
    # Basic validation
    if not job_spec.targets:
        errors.append("No targets specified")
    
    if job_spec.pps <= 0:
        errors.append("PPS must be positive")
    elif job_spec.pps > 10000:
        warnings.append("High PPS rate detected")
    
    if job_spec.packet_size <= 0:
        errors.append("Packet size must be positive")
    elif job_spec.packet_size > 65507:
        errors.append("Packet size too large (max 65507)")
    
    # Port validation
    if job_spec.dst_port and not validate_port(job_spec.dst_port):
        errors.append("Invalid destination port")
    
    if job_spec.src_port and job_spec.src_port > 0 and not validate_port(job_spec.src_port):
        errors.append("Invalid source port")
    
    # Interface validation
    if job_spec.iface and not validate_interface_name(job_spec.iface):
        errors.append("Invalid interface name")
    
    # Spoof validation
    if job_spec.spoof_source and not job_spec.source_ip:
        errors.append("Source IP required when spoofing is enabled")
    
    # Duration validation
    if job_spec.duration < 0:
        errors.append("Duration cannot be negative")
    elif job_spec.duration > 86400:  # 24 hours
        errors.append("Duration too long (max 24 hours)")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    }