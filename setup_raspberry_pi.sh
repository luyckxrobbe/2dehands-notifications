#!/bin/bash
"""
Raspberry Pi setup script for the bike monitoring system.
"""

echo "🍓 Setting up bike monitoring system for Raspberry Pi..."
echo ""

# Check if we're on a Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    echo "⚠️  Warning: This doesn't appear to be a Raspberry Pi"
    echo "   The optimizations may not be necessary"
    echo ""
fi

# Create virtual environment
echo "📦 Creating Python virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
echo "📥 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Install Playwright browsers (optimized for Pi)
echo "🌐 Installing Playwright browsers (this may take a while on Pi)..."
playwright install chromium

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p backups
mkdir -p logs

# Set up systemd service (optional)
echo "⚙️  Setting up systemd service..."
cat > bike-monitor-pi.service << EOF
[Unit]
Description=Bike Monitor Pi
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=$(pwd)
Environment=PATH=$(pwd)/.venv/bin
ExecStart=$(pwd)/.venv/bin/python $(pwd)/run_monitors_pi.py configs/
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

echo "✅ Raspberry Pi setup complete!"
echo ""
echo "Next steps:"
echo "1. Copy your .env file with Telegram credentials"
echo "2. Test the system: python run_monitors_pi.py configs/"
echo "3. Optional: Install as service:"
echo "   sudo cp bike-monitor-pi.service /etc/systemd/system/"
echo "   sudo systemctl enable bike-monitor-pi"
echo "   sudo systemctl start bike-monitor-pi"
echo ""
echo "Pi-optimized features enabled:"
echo "  - Longer intervals (10+ minutes)"
echo "  - Reduced page counts (1-3 pages)"
echo "  - Memory-optimized browser settings"
echo "  - Sequential execution with delays"
echo "  - Automatic resource cleanup"