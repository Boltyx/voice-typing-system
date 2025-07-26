#!/usr/bin/env python3
"""
Voice Typing System - Main Application
A background application for voice-to-text transcription with global hotkey support.
"""

import sys
import threading
import time
import json
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QAction
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from pynput import keyboard
import logging
import subprocess

from config_manager import ConfigManager
from audio_manager import AudioManager
from transcription_service import TranscriptionService
from text_insertion import TextInsertion

class TranscriptionWorker(QThread):
    """Worker thread for handling transcription."""
    
    transcription_complete = pyqtSignal(str, bool)  # text, success
    
    def __init__(self, transcription_service, audio_file, metadata, session_dir):
        super().__init__()
        self.transcription_service = transcription_service
        self.audio_file = audio_file
        self.metadata = metadata
        self.session_dir = session_dir
        self._running = True
    
    def run(self):
        """Run transcription in background thread."""
        try:
            if not self._running:
                return
                
            # Send audio to transcription service
            transcript = self.transcription_service.transcribe_audio(self.audio_file, self.metadata)
            
            if not self._running:
                return
                
            if transcript:
                # Save transcript
                self.transcription_service.save_transcript(self.session_dir, transcript, self.metadata)
                self.transcription_complete.emit(transcript, True)
            else:
                # Save failed transcription metadata
                self.transcription_service.save_failed_transcription(
                    self.session_dir, self.metadata, "Transcription failed"
                )
                self.transcription_complete.emit("", False)
                
        except Exception as e:
            if not self._running:
                return
                
            error_msg = str(e)
            if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                error_msg = f"TRANSCRIPTION TIMEOUT: {error_msg}"
                logging.error(f"TRANSCRIPTION TIMEOUT in worker: {error_msg}")
            else:
                logging.error(f"Error in transcription worker: {error_msg}")
            
            self.transcription_service.save_failed_transcription(
                self.session_dir, self.metadata, error_msg
            )
            self.transcription_complete.emit("", False)
    
    def stop(self):
        """Stop the worker thread gracefully."""
        self._running = False

class StateManager(dict):
    def __init__(self, path):
        self.path = Path(path)
        if self.path.exists():
            with open(self.path, 'r') as f:
                self.update(json.load(f))
    def save(self):
        with open(self.path, 'w') as f:
            json.dump(self, f)

class VoiceTypingSystem(QApplication):
    """Main application class for Voice Typing System."""
    
    def __init__(self, argv):
        super().__init__(argv)
        
        # Initialize components
        self.config = ConfigManager()
        self.state_manager = StateManager(Path.home() / '.local/share/voice-typing-system/state.json')
        self.audio_manager = AudioManager(self.config, state_manager=self.state_manager)
        self.transcription_service = TranscriptionService(self.config)
        self.text_insertion = TextInsertion()
        
        # Application state
        self.recording = False
        self.transcription_worker = None
        self.activated = True  # Default to activated
        self.processing = False  # True when transcribing
        self.error_state = False  # True when in error state
        self.idle = True # True when idle
        
        # Load activation state from config
        self.load_activation_state()
        
        # Setup UI
        self.setup_system_tray()
        self.setup_hotkey_listener()
        
        logging.info("Voice Typing System initialized")
    
    def load_activation_state(self):
        """Load activation state from config file."""
        try:
            state_file = Path.home() / '.local/share/voice-typing-system/state.json'
            if state_file.exists():
                with open(state_file, 'r') as f:
                    state = json.load(f)
                    self.activated = state.get('activated', True)
                    logging.info(f"Loaded activation state: {'activated' if self.activated else 'deactivated'}")
        except Exception as e:
            logging.warning(f"Failed to load activation state: {e}")
            self.activated = True  # Default to activated
    
    def save_activation_state(self):
        """Save activation state to config file."""
        try:
            state_dir = Path.home() / '.local/share/voice-typing-system'
            state_dir.mkdir(parents=True, exist_ok=True)
            state_file = state_dir / 'state.json'
            
            with open(state_file, 'w') as f:
                json.dump({'activated': self.activated}, f)
                logging.info(f"Saved activation state: {'activated' if self.activated else 'deactivated'}")
        except Exception as e:
            logging.error(f"Failed to save activation state: {e}")
    
    def update_tray_icon(self):
        """Update the tray icon based on current state."""
        # Determine color based on state
        if not self.activated:
            # Deactivated - Grey
            color = QColor('#808080')
        elif self.error_state:
            # Error - Red
            color = QColor('#ff0000')
        elif self.processing:
            # Processing/Transcribing - Dull Yellow
            color = QColor(100, 100, 0)
        elif self.recording:
            # Recording - Bright Yellow (pulsing is handled by a timer)
            color = QColor(255, 255, 0)
        elif self.idle:
            # Active and ready - Green
            color = QColor('#00ff00')
        else:
            # Default to green if state is ambiguous
            color = QColor('#00ff00')

        icon = self.create_simple_icon(color)
        self.tray_icon.setIcon(icon)
    
    def create_simple_icon(self, color):
        """Create a simple solid color icon."""
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(color)
        painter.setPen(color)
        painter.drawEllipse(4, 4, 24, 24)
        painter.end()
        return QIcon(pixmap)
    
    def setup_hotkey_listener(self):
        """Setup global hotkey listener using pynput HotKey."""
        # Only setup listener if activated
        if not self.activated:
            return
            
        def on_hotkey():
            logging.info("Hotkey triggered: Ctrl+Shift+T")
            if self.activated:  # Double-check activation state
                self.toggle_recording()
        
        # Create hotkey using pynput's HotKey class
        self.hotkey = keyboard.HotKey(
            keyboard.HotKey.parse('<ctrl>+<shift>+t'),
            on_hotkey
        )
        
        # Setup listener with canonical key handling
        def for_canonical(f):
            return lambda k: f(self.keyboard_listener.canonical(k))
        
        self.keyboard_listener = keyboard.Listener(
            on_press=for_canonical(self.hotkey.press),
            on_release=for_canonical(self.hotkey.release)
        )
        self.keyboard_listener.start()
        
        logging.info("Hotkey listener started: <ctrl>+<shift>+t")
    
    def toggle_recording(self):
        """Toggle recording state."""
        if self.recording:
            self.stop_recording()
        else:
            self.start_recording()
    
    def start_recording(self):
        """Start audio recording."""
        if self.recording or not self.activated:
            return
        self.recording = True
        self.error_state = False  # Clear any previous errors
        self.idle = False
        self.record_action.setText("Stop Recording")
        self.update_tray_icon()
        # Preload the model in background thread for faster transcription
        self.preload_model_async()
        # Start recording
        self.audio_manager.start_recording(self.on_recording_complete)
        self.update_menu_state() # Update menu to show abort option
        logging.info("Recording started")
    
    def stop_recording(self):
        """Stop audio recording and proceed with transcription."""
        if not self.recording:
            return
        self.recording = False
        self.record_action.setText("Start Recording")
        self.audio_manager.stop_recording(aborted=False)
        self.processing = True # Set processing state immediately
        self.update_tray_icon()
        self.update_menu_state()
        logging.info("Recording stopped for transcription")
    
    def abort_recording(self):
        """Abort audio recording without transcription."""
        if not self.recording:
            return
        self.recording = False
        self.record_action.setText("Start Recording")
        self.audio_manager.stop_recording(aborted=True)
        self.idle = True # Return to idle state
        self.update_tray_icon()
        self.update_menu_state()
        logging.info("Recording aborted by user")

    def preload_model_async(self):
        """Preload the model in a background thread."""
        def preload_worker():
            try:
                self.transcription_service.preload_model()
            except Exception as e:
                logging.error(f"Error in preload worker: {e}")
        
        # Start preload in background thread
        preload_thread = threading.Thread(target=preload_worker)
        preload_thread.daemon = True
        preload_thread.start()
    
    def on_recording_complete(self, audio_file, metadata):
        """Called when audio recording is complete."""
        if audio_file is None:
            logging.error("Audio recording failed or no audio captured")
            if 'error' in metadata:
                logging.error(f"Recording error: {metadata['error']}")
            # Set error state
            self.error_state = True
            self.processing = False
            self.update_tray_icon()
            # Show notification
            self.tray_icon.showMessage(
                "Voice Typing System",
                "Recording failed - no audio captured",
                QSystemTrayIcon.MessageIcon.Warning,
                3000
            )
            return
        logging.info(f"Recording complete: {audio_file}")
        # Notify if clipping detected
        if metadata.get('clipping_detected'):
            percent = metadata.get('clipping_percent', 0.0)
            self.tray_icon.showMessage(
                "Voice Typing System",
                f"Warning: {percent:.2f}% of your recording is clipped. Consider lowering your microphone input level in system settings.",
                QSystemTrayIcon.MessageIcon.NoIcon,
                5000
            )
        # Set processing state (solid yellow)
        self.processing = True
        self.idle = False
        self.update_tray_icon()
        # Get session directory
        session_dir = audio_file.parent
        # Start transcription in background thread
        self.transcription_worker = TranscriptionWorker(
            self.transcription_service, audio_file, metadata, session_dir
        )
        self.transcription_worker.transcription_complete.connect(self.on_transcription_complete)
        self.transcription_worker.start()
    
    def on_transcription_complete(self, transcript, success):
        """Called when transcription is complete."""
        # Clear processing state
        self.processing = False
        self.idle = True
        
        if success and transcript:
            logging.info(f"Transcription successful: {len(transcript)} characters")
            
            # Insert text into focused field
            insertion_method = self.text_insertion.insert_text(transcript)

            # Determine session_dir from the worker
            session_dir = self.transcription_worker.session_dir if self.transcription_worker else None

            if insertion_method:
                logging.info("Text inserted successfully")

                # Update metadata with insertion method
                if session_dir:
                    self.transcription_service.update_metadata(
                        session_dir, {'insertion_method': insertion_method}
                    )

                # Success - back to green
                self.error_state = False
                self.update_tray_icon()
            else:
                logging.warning("Failed to insert text - no text box in focus")
                # Not an error, just no focus - show notification
                self.error_state = False
                self.update_tray_icon()
                self.tray_icon.showMessage(
                    "Voice Typing System",
                    "Transcription complete, no text box in focus",
                    QSystemTrayIcon.MessageIcon.Information,
                    3000
                )
        else:
            logging.error("Transcription failed")
            # Set error state
            self.error_state = True
            self.update_tray_icon()
            
            # Show error notification
            self.tray_icon.showMessage(
                "Voice Typing System",
                "Transcription failed",
                QSystemTrayIcon.MessageIcon.Critical,
                3000
            )
    
    def quit(self):
        """Quit the application."""
        logging.info("Quitting Voice Typing System")
        
        # Stop recording if active
        if self.recording:
            self.stop_recording()
        
        # Cleanup transcription worker thread
        if self.transcription_worker and self.transcription_worker.isRunning():
            logging.info("Waiting for transcription worker to finish...")
            self.transcription_worker.stop()  # Signal the thread to stop gracefully
            self.transcription_worker.quit()
            self.transcription_worker.wait(5000)  # Wait up to 5 seconds
            if self.transcription_worker.isRunning():
                logging.warning("Transcription worker did not finish gracefully, terminating...")
                self.transcription_worker.terminate()
                self.transcription_worker.wait(2000)  # Wait up to 2 more seconds
        
        # Save activation state
        self.save_activation_state()
        
        # Cleanup
        self.audio_manager.cleanup()
        
        # Quit application
        super().quit()

    def setup_system_tray(self):
        """Setup system tray icon and menu."""
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setToolTip("Voice Typing System")
        self.tray_menu = QMenu()
        self.record_action = QAction("Start Recording", self)
        self.record_action.triggered.connect(self.toggle_recording)
        self.tray_menu.addAction(self.record_action)
        self.tray_menu.addSeparator()
        self.activate_action = QAction("Deactivate", self)
        self.activate_action.triggered.connect(self.toggle_activation)
        self.tray_menu.addAction(self.activate_action)
        self.device_menu = QMenu("Audio Device")
        self.update_device_menu()
        self.tray_menu.addMenu(self.device_menu)
        # Add open recording directory action
        open_dir_action = QAction("Open Recording Directory", self)
        open_dir_action.triggered.connect(self.open_recording_directory)
        self.tray_menu.addAction(open_dir_action)

        # Add Abort action (added near the bottom as requested)
        self.abort_action = QAction("Abort Transcription", self)
        self.abort_action.triggered.connect(self.abort_recording)
        self.tray_menu.addAction(self.abort_action)

        self.tray_menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit)
        self.tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(self.tray_menu)
        self.update_tray_icon()
        self.tray_icon.show()
        self.update_menu_state()

    def open_recording_directory(self):
        path = str(self.config.get_recording_directory().expanduser())
        try:
            if sys.platform.startswith('linux'):
                subprocess.Popen(['xdg-open', path])
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', path])
            elif sys.platform == 'win32':
                subprocess.Popen(['explorer', path])
            else:
                logging.error(f"Unsupported platform for opening directory: {sys.platform}")
        except Exception as e:
            logging.error(f"Failed to open recording directory: {e}")

    def toggle_activation(self):
        """Toggle the activation state."""
        self.activated = not self.activated
        self.save_activation_state()
        self.update_menu_state()
        self.update_tray_icon()
        if self.activated:
            logging.info("Voice Typing System activated")
            self.setup_hotkey_listener()
        else:
            logging.info("Voice Typing System deactivated")
            self.stop_recording()  # Stop any ongoing recording
            if hasattr(self, 'keyboard_listener'):
                self.keyboard_listener.stop()

    def update_menu_state(self):
        """Update menu items based on current state."""
        if self.activated:
            self.activate_action.setText("Deactivate")
            self.record_action.setEnabled(True)
        else:
            self.activate_action.setText("Activate")
            self.record_action.setEnabled(False)
        
        # Enable/disable abort action based on recording state
        self.abort_action.setEnabled(self.recording)
    
    def update_device_menu(self):
        """Update the audio device selection menu."""
        self.device_menu.clear()
        devices = self.audio_manager.get_device_list()
        current_device = self.audio_manager.current_device
        for device in devices:
            action = QAction(device['name'], self)
            action.setCheckable(True)
            action.setChecked(device['index'] == current_device)
            action.triggered.connect(lambda checked, idx=device['index']: self.set_audio_device(idx))
            self.device_menu.addAction(action)

    def set_audio_device(self, device_index):
        """Set the audio input device."""
        self.audio_manager.set_device(device_index)
        self.update_device_menu()
        logging.info(f"Audio device set to: {self.audio_manager.get_current_device_name()}")

def main():
    """Main entry point."""
    app = VoiceTypingSystem(sys.argv)
    
    # Set application properties
    app.setApplicationName("Voice Typing System")
    app.setApplicationVersion("1.0.0")
    app.setQuitOnLastWindowClosed(False)
    
    # Run application
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 
    main() 