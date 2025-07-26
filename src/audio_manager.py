"""
Audio manager for Voice Typing System.
Handles audio device detection, recording, and file management.
"""

import pyaudio
import wave
import threading
import time
from pathlib import Path
from typing import List, Dict, Optional, Callable, Union
import logging
from datetime import datetime
import numpy as np
from scipy.signal import resample_poly
from PyQt6.QtCore import QObject, pyqtSignal

class AudioManager(QObject):
    """Manages audio recording and device selection."""
    
    recording_finished = pyqtSignal(object, object)

    def __init__(self, config_manager, state_manager=None):
        """
        Initialize audio manager.
        
        Args:
            config_manager: Configuration manager instance
        """
        super().__init__()
        self.config = config_manager
        self.audio = pyaudio.PyAudio()
        self.recording = False
        self.recording_thread = None
        self.frames = []
        self.current_device = None
        self.audio_settings = self.config.get_audio_settings()
        self.state_manager = state_manager
        self.devices = self._get_audio_devices()
        self.last_device_index = None
        # Try to load last device from state
        if self.state_manager:
            self.last_device_index = self.state_manager.get('last_device_index')
        self._select_initial_device()
    
    def _get_audio_devices(self) -> Dict[int, Dict]:
        """Get list of available audio input devices."""
        devices = {}
        
        for i in range(self.audio.get_device_count()):
            try:
                device_info = self.audio.get_device_info_by_index(i)
                if int(device_info['maxInputChannels']) > 0:  # Input device
                    # Get the device's native sample rate
                    native_sample_rate = int(device_info['defaultSampleRate'])
                    
                    devices[i] = {
                        'name': device_info['name'],
                        'channels': device_info['maxInputChannels'],
                        'sample_rate': native_sample_rate,
                        'native_sample_rate': native_sample_rate  # Store native rate separately
                    }
                    logging.info(f"Found audio device {i}: {device_info['name']} (Sample rate: {native_sample_rate} Hz)")
            except Exception as e:
                logging.warning(f"Failed to get device {i} info: {e}")
        
        return devices
    
    def get_device_list(self) -> List[Dict]:
        """Get list of available audio devices for UI."""
        return [
            {'index': idx, 'name': info['name']}
            for idx, info in self.devices.items()
        ]
    
    def set_device(self, device_index: int):
        """Set the current audio device."""
        if device_index in self.devices:
            self.current_device = device_index
            if self.state_manager:
                self.state_manager['last_device_index'] = device_index
                self.state_manager.save()
            logging.info(f"Audio device set to: {self.devices[device_index]['name']}")
        else:
            logging.error(f"Invalid device index: {device_index}")
    
    def get_current_device_name(self) -> str:
        """Get the name of the current audio device."""
        if self.current_device is not None:
            return self.devices[self.current_device]['name']
        return "No device selected"
    
    def start_recording(self):
        """Start audio recording."""
        if self.recording:
            logging.warning("Recording already in progress")
            return
        
        if self.current_device is None:
            logging.error("No audio device selected")
            return
        
        self.recording = True
        self.frames = []
        
        # Start recording in a separate thread
        self.recording_thread = threading.Thread(
            target=self._record_audio,
        )
        self.recording_thread.start()
        
        logging.info("Audio recording started")
    
    def stop_recording(self, aborted: bool = False):
        """
        Stop audio recording.

        Args:
            aborted (bool): If True, the recording is aborted and not sent for transcription.
        """
        if not self.recording:
            logging.warning("No recording in progress")
            return
        
        self.recording = False
        self.aborted = aborted  # Store the aborted state
        
        if self.recording_thread:
            self.recording_thread.join()
        
        if aborted:
            logging.info("Audio recording aborted")
        else:
            logging.info("Audio recording stopped")
    
    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self.recording
    
    def _select_initial_device(self):
        # Try last device
        if self.last_device_index is not None and self.last_device_index in self.devices:
            self.current_device = self.last_device_index
            return
        # Try pulse
        for idx, info in self.devices.items():
            if 'pulse' in info['name'].lower():
                self.current_device = idx
                return
        # Fallback to first available
        if self.devices:
            self.current_device = list(self.devices.keys())[0]

    def _record_audio(self):
        """Internal method to record audio."""
        self.aborted = False  # Reset aborted state at start
        try:
            if self.current_device is None:
                raise ValueError("No audio device selected")
            device_info = self.devices[self.current_device]
            device_name = device_info['name']
            device_native_rate = device_info['native_sample_rate']
            target_rate = self.audio_settings['sample_rate']
            device_channels = min(device_info['channels'], self.audio_settings['channels'])
            chunk_size = self.audio_settings['chunk_size']
            # Try 16kHz first
            try:
                stream = self.audio.open(
                    format=pyaudio.paInt16,
                    channels=device_channels,
                    rate=target_rate,
                    input=True,
                    input_device_index=self.current_device,
                    frames_per_buffer=chunk_size
                )
                used_rate = target_rate
                logging.info(f"Opened device at 16kHz: {device_name}")
            except Exception as e:
                logging.warning(f"Failed to open device at 16kHz: {e}. Trying native rate {device_native_rate}.")
            stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=device_channels,
                rate=device_native_rate,
                input=True,
                input_device_index=self.current_device,
                frames_per_buffer=chunk_size
            )
            used_rate = device_native_rate
            logging.info(f"Opened device at native rate: {device_native_rate}")
            self.frames = []
            while self.recording:
                try:
                    data = stream.read(chunk_size, exception_on_overflow=False)
                    self.frames.append(data)
                except Exception as e:
                    logging.error(f"Error reading audio data: {e}")
                    break
            stream.stop_stream()
            stream.close()

            # Handle abort case
            if self.aborted:
                if self.config.get('recording.save_on_abort', True):
                    # Save the file but don't transcribe
                    self._save_audio_file(used_rate, device_channels)
                    logging.info("Recording aborted, audio saved.")
                else:
                    # Discard the file
                    logging.info("Recording aborted, audio discarded.")
                
                # We don't call on_recording_complete because it was aborted
                return

            # Save original file first
            audio_file, metadata = self._save_audio_file(used_rate, device_channels)
            logging.info(f"Audio file saved: {audio_file}")
            # If not 16kHz, resample and save as new file
            if used_rate != target_rate:
                try:
                    resampled_file = audio_file.parent / f"audio_16khz.{self.audio_settings['format']}"
                    self._resample_wav(audio_file, resampled_file, used_rate, target_rate, device_channels)
                    logging.info(f"Resampled audio saved: {resampled_file}")
                    # Optionally delete original
                    # audio_file.unlink()
                    self.recording_finished.emit(resampled_file, metadata)
                except Exception as e:
                    logging.error(f"Resampling failed: {e}. Keeping original file.")
                    self.recording_finished.emit(audio_file, metadata)
            else:
                self.recording_finished.emit(audio_file, metadata)
        except Exception as e:
            logging.error(f"Error during audio recording: {e}")
            self.recording = False
            self.recording_finished.emit(None, {'error': str(e)})
    
    def _save_audio_file(self, sample_rate, channels) -> tuple[Path, Dict]:
        """
        Save recorded audio to file.
        
        Returns:
            Tuple of (audio_file_path, metadata)
        """
        # Create timestamp for filename
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        recording_dir = self.config.get_recording_directory()
        session_dir = recording_dir / timestamp
        session_dir.mkdir(exist_ok=True)
        
        # Save audio file
        audio_file = session_dir / f"audio.{self.audio_settings['format']}"
        
        # Get the actual recording parameters used
        chunk_size = self.audio_settings['chunk_size']
        
        with wave.open(str(audio_file), 'wb') as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(self.audio.get_sample_size(pyaudio.paInt16))
            wf.setframerate(sample_rate)
            wf.writeframes(b''.join(self.frames))
        
        # Clipping detection
        audio_np = np.frombuffer(b''.join(self.frames), dtype=np.int16)
        clipped = np.sum((audio_np == 32767) | (audio_np == -32768))
        clip_percent = clipped / len(audio_np) * 100 if len(audio_np) > 0 else 0.0
        # Create metadata
        metadata = {
            'timestamp': timestamp,
            'device_name': self.get_current_device_name(),
            'device_index': self.current_device,
            'sample_rate': sample_rate,
            'channels': channels,
            'format': self.audio_settings['format'],
            'duration': float(len(self.frames) * chunk_size / sample_rate),
            'file_size': int(audio_file.stat().st_size),
            'status': 'recorded',
            'clipping_percent': float(clip_percent),
            'clipping_detected': bool(clip_percent > 0.5)
        }
        
        logging.info(f"Audio saved to: {audio_file}")
        return audio_file, metadata

    def _resample_wav(self, input_file: Path, output_file: Path, orig_rate: int, target_rate: int, channels: int):
        import wave
        with wave.open(str(input_file), 'rb') as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            n_frames = wf.getnframes()
            audio_data = wf.readframes(n_frames)
        audio_np = np.frombuffer(audio_data, dtype=np.int16)
        if n_channels > 1:
            audio_np = audio_np.reshape(-1, n_channels)
        # Resample
        resampled = resample_poly(audio_np, target_rate, orig_rate, axis=0).astype(np.int16)
        if n_channels > 1:
            resampled = resampled.reshape(-1)
        with wave.open(str(output_file), 'wb') as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sampwidth)
            wf.setframerate(target_rate)
            wf.writeframes(resampled.tobytes())
    
    def cleanup(self):
        """Clean up audio resources."""
        if self.recording:
            self.stop_recording()
        
        if self.audio:
            self.audio.terminate() 