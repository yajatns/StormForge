#!/bin/bash

# StormForge - Fix System Package Issues
# Run this first to fix the dpkg/apt issues

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

log "Fixing system package configuration issues..."

# Fix the debian module missing issue
log "Installing python3-debian to fix update-notifier-common..."
sudo apt install -y python3-debian || {
    warn "Direct install failed, trying alternative approach..."
    
    # Alternative: force configure the broken package
    log "Attempting to force-configure broken packages..."
    sudo dpkg --configure -a
    
    # If still failing, remove and reinstall
    if [ $? -ne 0 ]; then
        warn "Force configure failed, removing problematic package..."
        sudo apt remove --purge update-notifier-common -y
        sudo apt autoremove -y
        sudo apt autoclean
    fi
}

# Clean up package cache and fix any remaining issues
log "Cleaning package cache and fixing broken dependencies..."
sudo apt clean
sudo apt update --fix-missing
sudo apt install -f -y

# Try to reinstall the fixed packages
log "Attempting to reinstall update-notifier-common..."
sudo apt install -y update-notifier-common python3-debian

log "System package issues should now be resolved!"
log "You can now run the StormForge setup script."