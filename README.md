# Voice Typing System

A background application for voice-to-text transcription with global hotkey support. Records audio, sends it to a transcription API, and inserts the transcribed text into the currently focused input field.

## Features

- **Global Hotkey**: Press `Ctrl+Shift+T` to start/stop recording
- **System Tray Integration**: Always accessible via system tray icon
- **Visual Feedback**: Tray icon changes color (gray=idle, red=recording)
- **Audio Device Selection**: Right-click tray icon to select microphone
- **Local Storage**: All recordings and transcripts saved locally with metadata
- **Error Handling**: Graceful degradation with audio preservation
- **Auto-start**: Runs automatically on system boot

## Requirements

- Python 3.8+
- Linux with systemd
- PyQt6 for GUI
- Audio input device (microphone)

## Installation

1. **Clone or download the project**:
   ```bash
   cd ~/Projects/apps/voice-typing-system
   ```

2. **Run the installation script**:
   ```bash
   ./install.sh
   ```

3. **Configure your transcription API**:
   Edit `~/.local/share/voice-typing-system/config.json`:
   ```json
   {
     "api": {
       "endpoint": "http://your-server:port/transcribe"
     }
   }
   ```

4. **Start the service**:
   ```bash
   systemctl --user start voice-typing-system
   ```

## Usage

### Basic Operation

1. **Start Recording**: Press `Ctrl+Shift+T` or right-click tray icon → "Start Recording"
2. **Stop Recording**: Press `Ctrl+Shift+T` again or right-click tray icon → "Stop Recording"
3. **Text Insertion**: Transcribed text is automatically inserted into the focused input field

### System Tray Menu

- **Start/Stop Recording**: Toggle recording state
- **Audio Device**: Select your microphone from the list
- **Settings**: View configuration file location
- **Quit**: Exit the application

### Configuration

The application uses a hierarchical configuration system:

1. **Default Config**: `config/default_config.json` (included with application)
2. **User Config**: `~/.local/share/voice-typing-system/config.json` (user overrides)

#### Key Configuration Options

```json
{
  "api": {
    "endpoint": "http://localhost:8000/transcribe",
    "timeout": 30
  },
  "audio": {
    "sample_rate": 16000,
    "channels": 1,
    "format": "wav"
  },
  "recording": {
    "directory": "~/.local/share/voice-typing-system/recordings",
    "max_duration": 600
  },
  "hotkey": {
    "combination": "ctrl+shift+t"
  }
}
```

## File Structure

```
~/.local/share/voice-typing-system/
├── recordings/
│   ├── 2024-01-15_14-30-25/
│   │   ├── audio.wav          # Recorded audio file
│   │   ├── transcript.txt     # Transcribed text
│   │   └── metadata.json      # Recording metadata
│   └── ...
├── logs/
│   └── app.log               # Application logs
└── config.json              # User configuration
```

## Troubleshooting

### Service Management

- **Check service status**:
  ```bash
  systemctl --user status voice-typing-system
  ```

- **View logs**:
  ```bash
  journalctl --user -u voice-typing-system -f
  ```

- **Restart service**:
  ```bash
  systemctl --user restart voice-typing-system
  ```

### Common Issues

1. **No audio devices detected**:
   - Check microphone permissions
   - Verify audio device is working in other applications

2. **Hotkey not working**:
   - Check if another application is using the same hotkey
   - Verify keyboard permissions

3. **Transcription fails**:
   - Check API endpoint configuration
   - Verify network connectivity
   - Check API server logs

4. **Text not inserting**:
   - Ensure input field is focused
   - Check if application has clipboard access

### Development

To run the application in development mode:

```bash
cd ~/Projects/apps/voice-typing-system
source venv/bin/activate
python src/main.py
```

## API Integration

The application expects your transcription API to:

- Accept POST requests with audio files
- Accept multipart form data with 'audio' field
- Return transcribed text in response body (JSON or plain text)
- Support WAV, OGG, WebM, AAC, or MP3 formats

Example API response:
```json
{
  "transcript": "This is the transcribed text"
}
```

Or plain text:
```
This is the transcribed text
```

## License

This project is open source. Feel free to modify and distribute.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review the logs in `~/.local/share/voice-typing-system/logs/`
3. Create an issue in the project repository 