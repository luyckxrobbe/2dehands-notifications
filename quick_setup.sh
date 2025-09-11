#!/bin/bash
# Quick Setup Script for Bike Monitoring on Raspberry Pi
# Minimal setup without systemd service

set -e

echo "🚴‍♂️ Quick Bike Monitor Setup"
echo "=============================="

# Update system
echo "📦 Updating system..."
sudo apt update && sudo apt upgrade -y

# Install dependencies
echo "📦 Installing dependencies..."
sudo apt install -y python3 python3-pip chromium-browser

# Install Python packages
echo "🐍 Installing Python packages..."
pip3 install --user -r requirements.txt

# Install Playwright browsers
echo "🌐 Installing browser binaries..."
playwright install chromium

# Setup environment
echo "⚙️  Setting up environment..."
if [ ! -f .env ]; then
    echo "Please enter your Telegram bot credentials:"
    read -p "Bot Token: " bot_token
    read -p "Chat ID: " chat_id
    
    cat > .env << EOF
TELEGRAM_BOT_TOKEN=$bot_token
TELEGRAM_CHAT_ID=$chat_id
EOF
fi

# Make scripts executable
chmod +x *.py

echo ""
echo "✅ Setup complete!"
echo ""
echo "To start monitoring:"
echo "  python3 run_monitors.py configs/"
echo ""
