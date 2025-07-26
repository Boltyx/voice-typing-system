#!/bin/bash
# Voice Typing System Installation Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${GREEN}Voice Typing System Installation${NC}"
echo "=================================="

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed${NC}"
    exit 1
fi

# Create virtual environment
echo -e "${YELLOW}Creating virtual environment...${NC}"
cd "$SCRIPT_DIR"
python3 -m venv venv

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source venv/bin/activate

# Upgrade pip (now using the venv pip)
echo -e "${YELLOW}Upgrading pip...${NC}"
pip install --upgrade pip

# Install requirements
echo -e "${YELLOW}Installing dependencies...${NC}"
pip install -r requirements.txt

# Make main script executable
echo -e "${YELLOW}Making main script executable...${NC}"
chmod +x src/main.py

# Stop existing service if running
echo -e "${YELLOW}Stopping existing service if running...${NC}"
systemctl --user stop voice-typing-system.service 2>/dev/null || true

# Clear Python cache to ensure fresh code
echo -e "${YELLOW}Clearing Python cache...${NC}"
find . -name "*.pyc" -delete 2>/dev/null || true
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# Create systemd user service
echo -e "${YELLOW}Creating systemd user service...${NC}"
SERVICE_DIR="$HOME/.config/systemd/user"
mkdir -p "$SERVICE_DIR"

cat > "$SERVICE_DIR/voice-typing-system.service" << EOF
[Unit]
Description=Voice Typing System
After=graphical-session.target

[Service]
Type=simple
ExecStart=$SCRIPT_DIR/venv/bin/python $SCRIPT_DIR/src/main.py
Restart=on-failure
RestartSec=10
Environment=DISPLAY=:0

[Install]
WantedBy=default.target
EOF

# Enable and start the service
echo -e "${YELLOW}Enabling systemd user service...${NC}"
systemctl --user enable voice-typing-system.service

# Reload daemon and start service with new code
echo -e "${YELLOW}Reloading systemd daemon and starting service...${NC}"
systemctl --user daemon-reload
systemctl --user start voice-typing-system.service

echo -e "${GREEN}Installation completed successfully!${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Configure your transcription API endpoint in:"
echo "   ~/.local/share/voice-typing-system/config.json"
echo ""
echo "2. Start the service:"
echo "   systemctl --user start voice-typing-system"
echo ""
echo "3. Check service status:"
echo "   systemctl --user status voice-typing-system"
echo ""
echo "4. View logs:"
echo "   journalctl --user -u voice-typing-system -f"
echo ""
echo -e "${GREEN}The application will start automatically on login.${NC}"
echo -e "${GREEN}Use Ctrl+Shift+T to start/stop recording.${NC}" 