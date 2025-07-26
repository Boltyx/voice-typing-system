#!/usr/bin/env python3
"""
Manual transcription script for testing the API.
"""

import requests
import json
from pathlib import Path
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def manual_transcribe(audio_file_path: str):
    """Manually transcribe an audio file using the API."""
    
    audio_file = Path(audio_file_path)
    
    if not audio_file.exists():
        print(f"Error: Audio file does not exist: {audio_file}")
        return
    
    # Get file info
    file_size = audio_file.stat().st_size
    file_size_mb = file_size / (1024 * 1024)
    
    print(f"=== FILE INFO ===")
    print(f"File: {audio_file}")
    print(f"Size: {file_size:,} bytes ({file_size_mb:.2f} MB)")
    print(f"Exists: {audio_file.exists()}")
    print(f"Expected format: 16kHz WAV (optimized for Whisper)")
    
    # API endpoint (from config)
    api_endpoint = "http://10.0.0.46:5000/transcribe"
    timeout = 300  # 5 minutes timeout for large files (matches config)
    
    print(f"\n=== API REQUEST ===")
    print(f"Endpoint: {api_endpoint}")
    print(f"Timeout: {timeout} seconds")
    
    try:
        # Prepare the file for upload
        print(f"\n=== UPLOADING FILE ===")
        with open(audio_file, 'rb') as f:
            files = {'file': (audio_file.name, f, 'audio/wav')}
            
            print("Sending request to API...")
            print(f"File being uploaded: {audio_file.name}")
            
            # Send request to API
            response = requests.post(
                api_endpoint,
                files=files,
                timeout=timeout
            )
        
        print(f"\n=== API RESPONSE ===")
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Content Length: {len(response.content)} bytes")
        
        # Check response
        if response.status_code == 200:
            print(f"\n=== PARSING RESPONSE ===")
            try:
                # Try to parse JSON response
                result = response.json()
                print(f"JSON Response: {result}")
                transcript = result.get('text', response.text)
            except json.JSONDecodeError as e:
                print(f"JSON Decode Error: {e}")
                print(f"Raw Response Text: {response.text[:500]}...")
                # If not JSON, use response text directly
                transcript = response.text
            
            transcript = transcript.strip()
            print(f"\n=== TRANSCRIPTION RESULT ===")
            print(f"Transcript Length: {len(transcript)} characters")
            print(f"Transcript: {transcript}")
            
            # Save to manual_transcription.txt
            output_file = audio_file.parent / "manual_transcription.txt"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(transcript)
            
            print(f"\n=== SAVED TO ===")
            print(f"File: {output_file}")
            
        else:
            print(f"\n=== ERROR RESPONSE ===")
            print(f"Status: {response.status_code}")
            print(f"Response Text: {response.text}")
            print(f"Response Headers: {dict(response.headers)}")
            
    except requests.exceptions.Timeout as e:
        print(f"\n=== TIMEOUT ERROR ===")
        print(f"Request timed out after {timeout} seconds")
        print(f"Error: {e}")
    except requests.exceptions.ConnectionError as e:
        print(f"\n=== CONNECTION ERROR ===")
        print(f"Failed to connect to API endpoint: {api_endpoint}")
        print(f"Error: {e}")
    except Exception as e:
        print(f"\n=== UNEXPECTED ERROR ===")
        print(f"Error type: {type(e).__name__}")
        print(f"Error: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    audio_file = "/home/alfred/.local/share/voice-typing-system/recordings/2025-07-25_01-10-28/audio.wav"
    manual_transcribe(audio_file) 