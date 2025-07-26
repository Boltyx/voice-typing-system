#!/bin/bash
# Force Update Voice Typing System

set -e

echo "Force updating Voice Typing System..."

# Kill all related processes
echo "Killing all voice typing processes..."
pkill -f "voice-typing-system" || true
pkill -f "main.py" || true

# Stop systemd service
echo "Stopping systemd service..."
systemctl --user stop voice-typing-system.service 2>/dev/null || true

# Clear ALL Python cache
echo "Clearing Python cache..."
find . -name "*.pyc" -delete 2>/dev/null || true
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyo" -delete 2>/dev/null || true

# Wait a moment
sleep 2

# Reload daemon and restart
echo "Restarting service..."
systemctl --user daemon-reload
systemctl --user start voice-typing-system.service

echo "Force update completed!"
echo "Check status: systemctl --user status voice-typing-system.service" 