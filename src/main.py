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
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer
from pynput import keyboard
import logging
import subprocess
import pyperclip

from config_manager import ConfigManager
from audio_manager import AudioManager
from transcription_service import TranscriptionService
from text_insertion import TextInsertion
from notification_widget import NotificationWidget

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

class ManualTranscriptionWorker(QThread):
    """Worker thread for handling manual transcription."""
    
    transcription_complete = pyqtSignal(str, bool)  # text, success
    
    def __init__(self, transcription_service, audio_file):
        super().__init__()
        self.transcription_service = transcription_service
        self.audio_file = audio_file
        self.session_dir = audio_file.parent
    
    def run(self):
        """Run transcription in background thread."""
        try:
            transcript = self.transcription_service.transcribe_audio(self.audio_file, {})
            if transcript is not None:
                self.transcription_service.save_manual_transcript(self.session_dir, transcript, {})
                self.transcription_complete.emit(transcript, True)
            else:
                self.transcription_complete.emit("", False)
        except Exception as e:
            logging.error(f"Error in manual transcription worker: {e}")
            self.transcription_complete.emit("", False)

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
    
    # Signals for thread-safe UI updates
    start_recording_request = pyqtSignal()
    stop_recording_request = pyqtSignal()

    def __init__(self, argv):
        super().__init__(argv)
        
        # Connect signals to slots
        self.start_recording_request.connect(self.start_recording)
        self.stop_recording_request.connect(self.stop_recording)

        # Initialize components
        self.config = ConfigManager()
        self.state_manager = StateManager(Path.home() / '.local/share/voice-typing-system/state.json')
        self.audio_manager = AudioManager(self.config, state_manager=self.state_manager)
        self.transcription_service = TranscriptionService(self.config)
        self.text_insertion = TextInsertion()
        
        # Connect audio manager signal
        self.audio_manager.recording_finished.connect(self.on_recording_complete)

        # Application state
        self.state = 'IDLE'
        self.transcription_worker = None
        self.manual_transcription_worker = None
        self.activated = True  # Default to activated
        self.last_transcript_text = None # To store the last successful transcript
        
        # Pulse animation timer
        self.pulse_timer = QTimer(self)
        self.pulse_timer.timeout.connect(self._pulse_icon)
        self.pulse_state = False

        # Load activation state from config
        self.load_activation_state()
        
        # Setup UI
        self.setup_system_tray()
        self.setup_hotkey_listener()
        
        # Setup custom notification widget
        self.notification = NotificationWidget()

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
    
    def _pulse_icon(self):
        """Handle the pulsing animation for the recording icon."""
        # This function is now only responsible for the visual pulse
        logging.debug(f"PULSE: Timer fired. Current state: {self.state}")
        self.pulse_state = not self.pulse_state
        color = QColor(255, 255, 0) if self.pulse_state else QColor(200, 200, 0)
        self.tray_icon.setIcon(self.create_simple_icon(color))

    def update_visuals(self):
        """
        Centralized method to update all visuals based on the current state.
        This is the single source of truth for how the app looks.
        """
        logging.debug(f"VISUALS: Updating visuals for state: {self.state}")
        # Stop any running pulse timer by default
        if self.pulse_timer.isActive():
            logging.debug("VISUALS: Pulse timer is active, stopping it.")
            self.pulse_timer.stop()
        
        color = None
        if not self.activated:
            color = QColor('#808080') # Grey
        elif self.state == 'ERROR':
            color = QColor('#ff0000') # Red
        elif self.state == 'PROCESSING':
            color = QColor(100, 100, 0) # Dull yellow
        elif self.state == 'IDLE':
            color = QColor('#00ff00') # Green
        elif self.state == 'RECORDING':
            # For recording, we start the timer which handles its own icons.
            # Set initial bright state.
            logging.debug("VISUALS: State is RECORDING. Starting pulse timer.")
            self.pulse_state = True
            self.tray_icon.setIcon(self.create_simple_icon(QColor(255, 255, 0)))
            self.pulse_timer.start(500)
            return # Return early to not set a static icon
        
        if color:
            self.tray_icon.setIcon(self.create_simple_icon(color))
            logging.debug(f"VISUALS: Set static icon to color: {color.name()}")

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
        """Thread-safe method to request a recording state change."""
        if self.state == 'RECORDING':
            self.stop_recording_request.emit()
        else:
            self.start_recording_request.emit()
    
    def start_recording(self):
        """Start audio recording. MUST be called from the main GUI thread."""
        if self.state == 'RECORDING' or not self.activated:
            return
        
        # Hide any existing notification before starting a new recording
        if self.notification.isVisible():
            self.notification.hide()

        logging.debug("ACTION: Start recording requested.")
        self.state = 'RECORDING'
        self.update_visuals()
        self.record_action.setText("Stop Recording")
        self.update_menu_state()
        
        # Preload the model in background thread for faster transcription
        self.preload_model_async()
        # Start recording
        self.audio_manager.start_recording()
        logging.info("Recording started")
    
    def stop_recording(self):
        """Stop audio recording and proceed with transcription. MUST be called from the main GUI thread."""
        if self.state != 'RECORDING':
            return
        
        logging.debug("ACTION: Stop recording requested.")
        self.state = 'PROCESSING'
        self.update_visuals()
        self.record_action.setText("Start Recording")
        self.audio_manager.stop_recording(aborted=False)
        self.update_menu_state()
        logging.info("Recording stopped for transcription")
    
    def abort_recording(self):
        """Abort audio recording without transcription."""
        if self.state != 'RECORDING':
            return
        
        logging.debug("ACTION: Abort recording requested.")
        self.state = 'IDLE'
        self.update_visuals()
        self.record_action.setText("Start Recording")
        self.audio_manager.stop_recording(aborted=True)
        self.update_menu_state()
        logging.info("Recording aborted by user")

    def on_manual_transcription_complete(self, transcript, success):
        """Called when a manual transcription is complete."""
        if success:
            self.last_transcript_text = transcript
            self.notification.show_message("Manual transcription complete.\nReady to be copied from clipboard.")
            logging.info("Manual transcription successful.")
        else:
            self.notification.show_message("Manual transcription failed.")
            logging.error("Manual transcription failed.")

        self.state = 'IDLE'
        self.update_visuals()
        self.update_menu_state()

    def transcribe_audio_file(self, audio_file: Path):
        """Starts a manual transcription for a given audio file."""
        if not audio_file or not audio_file.exists():
            self.notification.show_message("Audio file not found.")
            return

        self.state = 'PROCESSING'
        self.update_visuals()
        self.update_menu_state()

        self.manual_transcription_worker = ManualTranscriptionWorker(self.transcription_service, audio_file)
        self.manual_transcription_worker.transcription_complete.connect(self.on_manual_transcription_complete)
        self.manual_transcription_worker.start()

    def transcribe_latest_file(self):
        """Finds and transcribes the most recent audio file."""
        recording_dir = self.config.get_recording_directory()
        try:
            # Find the most recent session directory
            session_dirs = [d for d in recording_dir.iterdir() if d.is_dir()]
            if not session_dirs:
                self.notification.show_message("No recordings found.")
                return

            latest_dir = max(session_dirs, key=lambda d: d.stat().st_mtime)
            
            # Prefer the resampled 16kHz file if it exists
            audio_file_16khz = latest_dir / "audio_16khz.wav"
            audio_file_orig = latest_dir / "audio.wav"

            if audio_file_16khz.exists():
                self.transcribe_audio_file(audio_file_16khz)
            elif audio_file_orig.exists():
                self.transcribe_audio_file(audio_file_orig)
            else:
                self.notification.show_message(f"No audio file found in {latest_dir.name}.")

        except Exception as e:
            logging.error(f"Error finding latest file: {e}")
            self.notification.show_message("Error finding latest recording.")

    def transcribe_chosen_file(self):
        """Opens a file dialog to choose a file to transcribe."""
        from PyQt6.QtWidgets import QFileDialog

        # The QFileDialog must be created with a parent widget
        file_dialog = QFileDialog(None)
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        file_dialog.setNameFilter("Audio files (*.wav *.mp3 *.flac)")
        
        if file_dialog.exec():
            filenames = file_dialog.selectedFiles()
            if filenames:
                self.transcribe_audio_file(Path(filenames[0]))

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
        # This function is now guaranteed to run in the main GUI thread
        if audio_file is None:
            logging.error("Audio recording failed or no audio captured")
            if 'error' in metadata:
                logging.error(f"Recording error: {metadata['error']}")
            
            logging.debug("EVENT: Recording complete with failure.")
            self.state = 'ERROR'
            self.update_visuals()
            # Show notification
            self.notification.show_message("Recording failed - no audio captured")
            return
        logging.info(f"Recording complete: {audio_file}")
        # Notify if clipping detected
        if metadata.get('clipping_detected'):
            percent = metadata.get('clipping_percent', 0.0)
            message = f"Warning: {percent:.2f}% of your recording is clipped.\nConsider lowering your microphone input level."
            self.notification.show_message(message)
            logging.info(f"Clipping detected: {percent:.2f}%")
        
        logging.debug("EVENT: Recording complete with success.")
        self.state = 'PROCESSING'
        self.update_visuals()

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
        if success and transcript:
            logging.debug(f"EVENT: Transcription complete with success. Length: {len(transcript)}")
            self.last_transcript_text = transcript
            
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
                self.state = 'IDLE'
            else:
                logging.warning("Failed to insert text - no text box in focus")
                self.state = 'IDLE'
                self.notification.show_message("Transcription complete, no text box in focus")
        else:
            logging.debug("EVENT: Transcription complete with failure.")
            logging.error("Transcription failed")
            self.state = 'ERROR'
        
        self.update_visuals()
        self.update_menu_state()
            
    def quit(self):
        """Quit the application."""
        logging.info("Quitting Voice Typing System")
        
        # Stop recording if active
        if self.state == 'RECORDING':
            # Use the signal to ensure thread safety, although quit is usually from UI
            self.stop_recording_request.emit()

        if self.pulse_timer.isActive():
            self.pulse_timer.stop()  # Ensure timer is stopped on quit
        
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

        # Manual Transcribe submenu
        self.manual_transcribe_menu = self.tray_menu.addMenu("Manual Transcribe")
        latest_action = QAction("Transcribe Latest File", self)
        latest_action.triggered.connect(self.transcribe_latest_file)
        self.manual_transcribe_menu.addAction(latest_action)
        choose_action = QAction("Choose File...", self)
        choose_action.triggered.connect(self.transcribe_chosen_file)
        self.manual_transcribe_menu.addAction(choose_action)

        # Add "Copy to Clipboard" action
        self.copy_to_clipboard_action = QAction("Add latest to clipboard", self)
        self.copy_to_clipboard_action.triggered.connect(self.copy_last_transcript_to_clipboard)
        self.tray_menu.addAction(self.copy_to_clipboard_action)

        # Add Abort action (added near the bottom as requested)
        self.abort_action = QAction("Abort Transcription", self)
        self.abort_action.triggered.connect(self.abort_recording)
        self.tray_menu.addAction(self.abort_action)

        self.tray_menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit)
        self.tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(self.tray_menu)
        self.update_visuals()
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
        self.update_visuals()
        if self.activated:
            logging.info("Voice Typing System activated")
            self.setup_hotkey_listener()
        else:
            logging.info("Voice Typing System deactivated")
            if self.state == 'RECORDING':
                self.stop_recording_request.emit()  # Use signal for thread safety
            if hasattr(self, 'keyboard_listener'):
                self.keyboard_listener.stop()

    def copy_last_transcript_to_clipboard(self):
        """Copies the last successful transcript to the clipboard."""
        if self.last_transcript_text:
            pyperclip.copy(self.last_transcript_text)
            self.notification.show_message("Last transcript copied to clipboard.")
            logging.info("Copied last transcript to clipboard.")
        else:
            logging.warning("Attempted to copy last transcript, but none exists.")

    def update_menu_state(self):
        """Update menu items based on current state."""
        if self.activated:
            self.activate_action.setText("Deactivate")
            self.record_action.setEnabled(True)
        else:
            self.activate_action.setText("Activate")
            self.record_action.setEnabled(False)
        
        # Enable/disable submenus based on state
        self.manual_transcribe_menu.setEnabled(self.state == 'IDLE')
        self.abort_action.setEnabled(self.state == 'RECORDING')
        self.copy_to_clipboard_action.setEnabled(self.last_transcript_text is not None)
    
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