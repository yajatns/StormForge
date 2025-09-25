"""
Network validation utilities
"""

import ipaddress
from typing import List, Set, Tuple
import re
from netaddr import IPNetwork, IPSet
import structlog

from app.config import settings

logger = structlog.get_logger()


class NetworkValidator:
    """Network validation and allowlist/denylist management"""
    
    def __init__(self):
        self.allowed_ranges: IPSet = IPSet()
        self.blocked_ranges: IPSet = IPSet()
        self.allowed_broadcast_ranges: IPSet = IPSet()
        
        # Initialize default blocked ranges
        for cidr in settings.default_blocked_ranges:
            try:
                self.blocked_ranges.add(IPNetwork(cidr))
            except Exception as e:
                logger.warning("Invalid default blocked range", cidr=cidr, error=str(e))
        
        # Initialize allowed broadcast ranges
        for cidr in settings.allowed_broadcast_ranges:
            try:
                self.allowed_broadcast_ranges.add(IPNetwork(cidr))
            except Exception as e:
                logger.warning("Invalid allowed broadcast range", cidr=cidr, error=str(e))
    
    def update_allowlist(self, allowed_cidrs: List[str]):
        """Update the allowlist with new CIDR ranges"""
        self.allowed_ranges = IPSet()
        for cidr in allowed_cidrs:
            try:
                self.allowed_ranges.add(IPNetwork(cidr))
            except Exception as e:
                logger.warning("Invalid allowlist CIDR", cidr=cidr, error=str(e))
    
    def update_blocklist(self, blocked_cidrs: List[str]):
        """Update the blocklist with new CIDR ranges"""
        self.blocked_ranges = IPSet()
        
        # Always include default blocked ranges
        for cidr in settings.default_blocked_ranges:
            try:
                self.blocked_ranges.add(IPNetwork(cidr))
            except Exception as e:
                logger.warning("Invalid default blocked range", cidr=cidr, error=str(e))
        
        # Add custom blocked ranges
        for cidr in blocked_cidrs:
            try:
                self.blocked_ranges.add(IPNetwork(cidr))
            except Exception as e:
                logger.warning("Invalid blocklist CIDR", cidr=cidr, error=str(e))
    
    def validate_target(self, target: str) -> Tuple[bool, str]:
        """
        Validate a single target (IP or CIDR)
        Returns (is_valid, error_message)
        """
        try:
            # Parse target as IP or CIDR
            if '/' in target:
                network = IPNetwork(target)
                ip_to_check = network.network
                is_broadcast = network.size > 1
            else:
                ip_to_check = ipaddress.ip_address(target)
                is_broadcast = False
            
            # Check if it's blocked
            if ip_to_check in self.blocked_ranges:
                return False, f"Target {target} is in blocked range"
            
            # Check if broadcast/multicast is allowed
            if is_broadcast or ip_to_check.is_multicast:
                if ip_to_check not in self.allowed_broadcast_ranges:
                    return False, f"Broadcast/multicast target {target} not in allowed ranges"
            
            # Check if it's in allowlist (if allowlist is configured)
            if self.allowed_ranges and ip_to_check not in self.allowed_ranges:
                return False, f"Target {target} not in allowed ranges"
            
            return True, ""
            
        except Exception as e:
            return False, f"Invalid target format: {target} ({str(e)})"
    
    def validate_targets(self, targets: List[str]) -> Tuple[bool, List[str]]:
        """
        Validate a list of targets
        Returns (all_valid, error_messages)
        """
        errors = []
        
        for target in targets:
            is_valid, error = self.validate_target(target)
            if not is_valid:
                errors.append(error)
        
        return len(errors) == 0, errors
    
    def is_private_range(self, target: str) -> bool:
        """Check if target is in private IP ranges"""
        try:
            if '/' in target:
                network = IPNetwork(target)
                ip_to_check = network.network
            else:
                ip_to_check = ipaddress.ip_address(target)
            
            return ip_to_check.is_private
        except:
            return False


# Global validator instance
network_validator = NetworkValidator()


def validate_ip_address(ip_str: str) -> bool:
    """Validate IP address format"""
    try:
        ipaddress.ip_address(ip_str)
        return True
    except ValueError:
        return False


def validate_cidr(cidr_str: str) -> bool:
    """Validate CIDR format"""
    try:
        IPNetwork(cidr_str)
        return True
    except:
        return False


def validate_port(port: int) -> bool:
    """Validate port number"""
    return 1 <= port <= 65535


def validate_interface_name(iface: str) -> bool:
    """Validate network interface name"""
    if not iface:
        return False
    
    # Basic interface name validation (Linux style)
    pattern = r'^[a-zA-Z0-9\-_\.]+$'
    return bool(re.match(pattern, iface)) and len(iface) <= 15


def sanitize_payload(payload: str) -> str:
    """Sanitize payload to prevent injection attacks"""
    if not payload:
        return ""
    
    # Remove potentially dangerous characters
    dangerous_chars = ['&', ';', '|', '`', '$', '(', ')', '{', '}', '[', ']', '<', '>']
    sanitized = payload
    
    for char in dangerous_chars:
        sanitized = sanitized.replace(char, '')
    
    # Limit length
    return sanitized[:1024]