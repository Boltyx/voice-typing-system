#!/usr/bin/env python3
"""
Test script to verify the audio overflow fix.
"""

import pyaudio
import time
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_device_with_adaptive_chunk_size(device_index, device_name, sample_rate):
    """Test a device with adaptive chunk size."""
    audio = pyaudio.PyAudio()
    
    # Calculate appropriate chunk size
    base_chunk_size = 1024
    if sample_rate > 32000:
        chunk_size = max(base_chunk_size * 2, 2048)
    else:
        chunk_size = base_chunk_size
    
    print(f"Testing {device_name} ({sample_rate} Hz) with chunk size: {chunk_size}")
    
    try:
        stream = audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=sample_rate,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=chunk_size
        )
        
        print("✓ Stream opened successfully")
        
        # Record for 2 seconds
        frames = []
        start_time = time.time()
        
        while time.time() - start_time < 2:
            try:
                data = stream.read(chunk_size, exception_on_overflow=False)
                frames.append(data)
            except Exception as e:
                print(f"✗ Error reading audio: {e}")
                break
        
        print(f"✓ Recorded {len(frames)} chunks successfully")
        
        stream.stop_stream()
        stream.close()
        
    except Exception as e:
        print(f"✗ Error opening stream: {e}")
    
    audio.terminate()

def main():
    """Test all input devices."""
    audio = pyaudio.PyAudio()
    
    print("=== Testing Audio Devices with Adaptive Chunk Sizes ===")
    
    for i in range(audio.get_device_count()):
        try:
            device_info = audio.get_device_info_by_index(i)
            if int(device_info['maxInputChannels']) > 0:  # Input device
                sample_rate = int(device_info['defaultSampleRate'])
                device_name = device_info['name']
                
                print(f"\n--- Device {i}: {device_name} ---")
                test_device_with_adaptive_chunk_size(i, device_name, sample_rate)
                
        except Exception as e:
            print(f"Failed to test device {i}: {e}")
    
    audio.terminate()

if __name__ == "__main__":
    main() 