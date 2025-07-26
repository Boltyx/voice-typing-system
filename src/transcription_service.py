"""
Transcription service for Voice Typing System.
Handles communication with the transcription API.
"""

import requests
import json
from pathlib import Path
from typing import Dict, Optional
import logging
from datetime import datetime
import re

class TranscriptionService:
    """Handles communication with the transcription API."""
    
    def __init__(self, config_manager):
        """
        Initialize transcription service.
        
        Args:
            config_manager: Configuration manager instance
        """
        self.config = config_manager
        self.api_endpoint = self.config.get_api_endpoint()
        self.timeout = self.config.get('api.timeout', 30)
        self.preload_endpoint = self.api_endpoint.replace('/transcribe', '/preload')
    
    def _post_process_transcript(self, transcript: str) -> str:
        """Apply post-processing rules to the transcript."""
        # Remove "Thanks for watching" variants if enabled
        if self.config.get('post_processing.remove_thanks_for_watching', True):
            phrases_to_remove = [
                "Thank you for watching.",
                "Thanks for watching.",
                "Thank you for watching!",
                "Thanks for watching!",
            ]
            # Create a regex pattern to find any of these phrases at the end of the string,
            # ignoring leading/trailing whitespace.
            # The pattern looks for optional whitespace (\s*), then the phrase,
            # then optional punctuation (.), and finally the end of the string ($).
            for phrase in phrases_to_remove:
                # Escape special regex characters in the phrase
                safe_phrase = re.escape(phrase.strip().rstrip('!.'))
                pattern = r"[\s,]*" + safe_phrase + r"[\.!]?[\s]*$"
                
                # Use re.IGNORECASE to match "thank you" vs "Thank you"
                if re.search(pattern, transcript, re.IGNORECASE):
                    original_transcript = transcript
                    transcript = re.sub(pattern, "", transcript, flags=re.IGNORECASE)
                    logging.info(f"Removed '{phrase}' from transcript. Original: '{original_transcript}', New: '{transcript}'")
                    break # Stop after the first match

        return transcript.strip()

    def transcribe_audio(self, audio_file: Path, metadata: Dict) -> Optional[str]:
        """
        Send audio file to transcription API.
        
        Args:
            audio_file: Path to the audio file
            metadata: Recording metadata
            
        Returns:
            Transcribed text or None if failed
        """
        try:
            # Verify audio file exists
            if not audio_file.exists():
                logging.error(f"Audio file does not exist: {audio_file}")
                return None
            
            logging.info(f"Sending audio file to API: {audio_file}")
            
            # Prepare the file for upload
            with open(audio_file, 'rb') as f:
                files = {'file': (audio_file.name, f, 'audio/wav')}
                
                # Send request to API
                response = requests.post(
                    self.api_endpoint,
                    files=files,
                    timeout=self.timeout
                )
            
            # Check response
            if response.status_code == 200:
                try:
                    # Try to parse JSON response
                    result = response.json()
                    transcript = result.get('text', response.text)
                except json.JSONDecodeError:
                    # If not JSON, use response text directly
                    transcript = response.text
                
                # Apply post-processing
                processed_transcript = self._post_process_transcript(transcript.strip())
                
                logging.info(f"Transcription successful: {len(processed_transcript)} characters")
                return processed_transcript
            else:
                logging.error(f"API request failed with status {response.status_code}: {response.text}")
                return None
                
        except requests.exceptions.Timeout:
            logging.error(f"TRANSCRIPTION TIMEOUT: API request timed out after {self.timeout} seconds. File may be too large or API server is overloaded.")
            return None
        except requests.exceptions.ConnectionError:
            logging.error(f"Failed to connect to API endpoint: {self.api_endpoint}")
            return None
        except Exception as e:
            logging.error(f"Error during transcription: {e}")
            return None
    
    def preload_model(self):
        """
        Preload the Whisper model to improve transcription speed.
        
        Returns:
            True if preload was successful or already in progress, False otherwise
        """
        try:
            logging.info("Preloading Whisper model...")
            
            response = requests.post(
                self.preload_endpoint,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                status = result.get('status', 'unknown')
                message = result.get('message', 'No message')
                
                if status == 'success':
                    logging.info(f"Model preload: {message}")
                    return True
                else:
                    logging.warning(f"Model preload failed: {message}")
                    return False
            else:
                logging.error(f"Preload request failed with status {response.status_code}")
                return False
                
        except requests.exceptions.Timeout:
            logging.warning("PRELOAD TIMEOUT: Model preload request timed out after {self.timeout} seconds")
            return False
        except requests.exceptions.ConnectionError:
            logging.warning(f"Failed to connect to preload endpoint: {self.preload_endpoint}")
            return False
        except Exception as e:
            logging.error(f"Error during model preload: {e}")
            return False
    
    def save_transcript(self, session_dir: Path, transcript: str, metadata: Dict):
        """
        Save transcript to file.
        
        Args:
            session_dir: Directory for this recording session
            transcript: Transcribed text
            metadata: Recording metadata
        """
        try:
            # Save transcript
            transcript_file = session_dir / "transcript.txt"
            with open(transcript_file, 'w', encoding='utf-8') as f:
                f.write(transcript)
            
            # Update metadata
            metadata.update({
                'transcript_file': str(transcript_file),
                'transcript_length': len(transcript),
                'transcription_time': datetime.now().isoformat(),
                'status': 'transcribed'
            })
            
            # Save updated metadata
            metadata_file = session_dir / "metadata.json"
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logging.info(f"Transcript saved to: {transcript_file}")
            
        except Exception as e:
            logging.error(f"Error saving transcript: {e}")
    
    def update_metadata(self, session_dir: Path, new_data: Dict):
        """
        Update an existing metadata file with new information.

        Args:
            session_dir: Directory for the recording session.
            new_data: Dictionary with new key-value pairs to add.
        """
        metadata_file = session_dir / "metadata.json"
        if not metadata_file.exists():
            logging.warning(f"Metadata file not found, cannot update: {metadata_file}")
            return

        try:
            with open(metadata_file, 'r+') as f:
                metadata = json.load(f)
                metadata.update(new_data)
                f.seek(0)
                json.dump(metadata, f, indent=2)
                f.truncate()
            logging.info(f"Metadata updated with: {new_data}")
        except (IOError, json.JSONDecodeError) as e:
            logging.error(f"Failed to update metadata file {metadata_file}: {e}")

    def save_failed_transcription(self, session_dir: Path, metadata: Dict, error: str):
        """
        Save metadata for failed transcription.
        
        Args:
            session_dir: Directory for this recording session
            metadata: Recording metadata
            error: Error message
        """
        try:
            # Update metadata with error
            metadata.update({
                'transcription_error': error,
                'transcription_time': datetime.now().isoformat(),
                'status': 'transcription_failed'
            })
            
            # Save metadata
            metadata_file = session_dir / "metadata.json"
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logging.info(f"Failed transcription metadata saved to: {metadata_file}")
            
        except Exception as e:
            logging.error(f"Error saving failed transcription metadata: {e}") 