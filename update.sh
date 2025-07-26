#!/bin/bash
# Voice Typing System Update Script

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Voice Typing System Update${NC}"
echo "=============================="

# Stop existing service
echo -e "${YELLOW}Stopping existing service...${NC}"
systemctl --user stop voice-typing-system.service 2>/dev/null || true

# Clear Python cache
echo -e "${YELLOW}Clearing Python cache...${NC}"
find . -name "*.pyc" -delete 2>/dev/null || true
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# Reload daemon and restart service
echo -e "${YELLOW}Restarting service with updated code...${NC}"
systemctl --user daemon-reload
systemctl --user start voice-typing-system.service

echo -e "${GREEN}Update completed! Service is running with latest code.${NC}"
echo ""
echo "Check status: systemctl --user status voice-typing-system.service"
echo "View logs: journalctl --user -u voice-typing-system -f" 