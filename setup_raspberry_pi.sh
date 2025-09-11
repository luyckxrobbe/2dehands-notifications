#!/bin/bash
# Complete Raspberry Pi Setup Script for Bike Monitoring Project
# This script sets up everything needed to run the bike monitoring system

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if running on Raspberry Pi
is_raspberry_pi() {
    if [ -f /proc/device-tree/model ]; then
        grep -q "Raspberry Pi" /proc/device-tree/model
    else
        return 1
    fi
}

# Header
echo -e "${GREEN}"
echo "=========================================="
echo "  Bike Monitoring - Raspberry Pi Setup"
echo "=========================================="
echo -e "${NC}"

# Check if running on Raspberry Pi
if ! is_raspberry_pi; then
    print_warning "This script is designed for Raspberry Pi. Proceed anyway? (y/N)"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        print_error "Setup cancelled."
        exit 1
    fi
fi

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    print_error "Please don't run this script as root. It will use sudo when needed."
    exit 1
fi

# Update system packages
print_status "Updating system packages..."
sudo apt update
sudo apt upgrade -y
print_success "System packages updated"

# Install system dependencies
print_status "Installing system dependencies..."
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    chromium-browser \
    chromium-driver \
    fonts-liberation \
    libappindicator3-1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libxss1 \
    libnss3 \
    xdg-utils \
    htop \
    git \
    curl \
    wget \
    unzip \
    build-essential \
    libssl-dev \
    libffi-dev

print_success "System dependencies installed"

# Install Python dependencies
print_status "Installing Python dependencies..."
if [ -f requirements.txt ]; then
    pip3 install --user -r requirements.txt
    print_success "Python dependencies installed"
else
    print_error "requirements.txt not found in current directory"
    exit 1
fi

# Install Playwright browsers
print_status "Installing Playwright browser binaries..."
export PLAYWRIGHT_BROWSERS_PATH=0  # Install to system location
playwright install chromium
print_success "Playwright browsers installed"

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    print_status "Setting up environment variables..."
    echo ""
    echo "You need to configure your Telegram bot credentials:"
    echo ""
    echo "1. Create a bot with @BotFather on Telegram"
    echo "2. Get your bot token"
    echo "3. Get your chat ID by messaging @userinfobot"
    echo ""
    
    read -p "Enter your Telegram Bot Token: " bot_token
    read -p "Enter your Telegram Chat ID: " chat_id
    
    if [ -z "$bot_token" ] || [ -z "$chat_id" ]; then
        print_error "Both bot token and chat ID are required"
        exit 1
    fi
    
    cat > .env << EOF
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=$bot_token

# Your Telegram Chat ID
TELEGRAM_CHAT_ID=$chat_id

# Optional: OpenAI API Key for race bike classification
# OPENAI_API_KEY=your_openai_key_here
EOF
    
    print_success "Environment variables configured"
else
    print_status ".env file already exists, skipping configuration"
fi

# Set up proper permissions
print_status "Setting up file permissions..."
chmod +x *.py
chmod +x run_monitors.py
chmod +x bike_monitor.py
chmod +x setup_monitor.py
print_success "File permissions set"

# Create systemd service for auto-start (optional)
print_status "Creating systemd service for auto-start..."
cat > bike-monitor.service << EOF
[Unit]
Description=Bike Monitoring System
After=network.target
Wants=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
Environment=PATH=/usr/bin:/usr/local/bin
ExecStart=/usr/bin/python3 $(pwd)/run_monitors.py configs/
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo mv bike-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
print_success "Systemd service created"

# Test the installation
print_status "Testing installation..."
if python3 -c "import playwright, beautifulsoup4, telegram, openai" 2>/dev/null; then
    print_success "All Python dependencies are working"
else
    print_warning "Some Python dependencies may not be properly installed"
fi

# Create a simple test script
cat > test_setup.py << 'EOF'
#!/usr/bin/env python3
"""Test script to verify the installation"""

import sys
import os
from pathlib import Path

def test_imports():
    """Test if all required modules can be imported"""
    try:
        import playwright
        print("✓ Playwright imported successfully")
    except ImportError as e:
        print(f"✗ Playwright import failed: {e}")
        return False
    
    try:
        import bs4
        print("✓ BeautifulSoup4 imported successfully")
    except ImportError as e:
        print(f"✗ BeautifulSoup4 import failed: {e}")
        return False
    
    try:
        import telegram
        print("✓ Python-telegram-bot imported successfully")
    except ImportError as e:
        print(f"✗ Python-telegram-bot import failed: {e}")
        return False
    
    try:
        import openai
        print("✓ OpenAI imported successfully")
    except ImportError as e:
        print(f"✗ OpenAI import failed: {e}")
        return False
    
    return True

def test_config_files():
    """Test if config files exist"""
    config_dir = Path("configs")
    if not config_dir.exists():
        print("✗ Configs directory not found")
        return False
    
    config_files = list(config_dir.glob("*.json"))
    if not config_files:
        print("✗ No config files found in configs/")
        return False
    
    print(f"✓ Found {len(config_files)} config files")
    for config_file in config_files:
        print(f"  - {config_file.name}")
    
    return True

def test_env_file():
    """Test if .env file exists and has required variables"""
    env_file = Path(".env")
    if not env_file.exists():
        print("✗ .env file not found")
        return False
    
    with open(env_file, 'r') as f:
        content = f.read()
    
    if "TELEGRAM_BOT_TOKEN" not in content:
        print("✗ TELEGRAM_BOT_TOKEN not found in .env")
        return False
    
    if "TELEGRAM_CHAT_ID" not in content:
        print("✗ TELEGRAM_CHAT_ID not found in .env")
        return False
    
    print("✓ .env file configured correctly")
    return True

def main():
    print("Testing Bike Monitoring Setup...")
    print("=" * 40)
    
    success = True
    
    print("\n1. Testing Python imports:")
    if not test_imports():
        success = False
    
    print("\n2. Testing config files:")
    if not test_config_files():
        success = False
    
    print("\n3. Testing environment file:")
    if not test_env_file():
        success = False
    
    print("\n" + "=" * 40)
    if success:
        print("✓ All tests passed! Setup is complete.")
        print("\nTo start the monitoring system:")
        print("  python3 run_monitors.py configs/")
        print("\nTo enable auto-start on boot:")
        print("  sudo systemctl enable bike-monitor")
        print("  sudo systemctl start bike-monitor")
    else:
        print("✗ Some tests failed. Please check the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
EOF

chmod +x test_setup.py
python3 test_setup.py

# Final instructions
echo ""
echo -e "${GREEN}=========================================="
echo "  Setup Complete!"
echo "==========================================${NC}"
echo ""
echo "Your bike monitoring system is ready to use!"
echo ""
echo "Commands to get started:"
echo "  ${BLUE}python3 run_monitors.py configs/${NC}     - Start all monitors"
echo "  ${BLUE}python3 bike_monitor.py configs/config-2dehands.json${NC}  - Start single monitor"
echo "  ${BLUE}python3 test_setup.py${NC}               - Test installation"
echo ""
echo "Auto-start on boot:"
echo "  ${BLUE}sudo systemctl enable bike-monitor${NC}   - Enable auto-start"
echo "  ${BLUE}sudo systemctl start bike-monitor${NC}    - Start service now"
echo "  ${BLUE}sudo systemctl status bike-monitor${NC}   - Check service status"
echo ""
echo "Monitoring:"
echo "  ${BLUE}htop${NC}                                - Monitor system resources"
echo "  ${BLUE}sudo systemctl logs -f bike-monitor${NC} - View logs"
echo ""
echo "Files created:"
echo "  - .env (Telegram configuration)"
echo "  - /etc/systemd/system/bike-monitor.service (Auto-start service)"
echo "  - test_setup.py (Installation test)"
echo ""
print_success "Setup completed successfully!"
