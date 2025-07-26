#!/usr/bin/env python3
"""
Test script to verify UTF-8 text handling fix.
"""

import pyperclip
import pyautogui
import time

def test_utf8_text():
    """Test UTF-8 text handling."""
    
    # Test Swedish text (the problematic text from the user)
    swedish_text = "Men om vi testar shr s skulle vi kunna testa med den andra modellen som r en Qon-modell, det vill sga en kinesisk modell och den r ganska ny och s fr vi se vad som hnder."
    
    # Expected correct text
    expected_text = "Men om vi testar här så skulle vi kunna testa med den andra modellen som är en Qwen-modell, det vill säga en kinesisk modell och den är ganska ny och så får vi se vad som händer."
    
    print("=== Testing UTF-8 Text Handling ===")
    print(f"Original text: {swedish_text}")
    print(f"Expected text: {expected_text}")
    
    # Test pyperclip
    print("\n--- Testing pyperclip ---")
    try:
        pyperclip.copy(swedish_text)
        retrieved_text = pyperclip.paste()
        print(f"pyperclip copy/paste: {retrieved_text}")
        print(f"Match: {retrieved_text == swedish_text}")
    except Exception as e:
        print(f"pyperclip error: {e}")
    
    # Test with correct Swedish text
    print("\n--- Testing with correct Swedish text ---")
    try:
        pyperclip.copy(expected_text)
        retrieved_text = pyperclip.paste()
        print(f"pyperclip copy/paste: {retrieved_text}")
        print(f"Match: {retrieved_text == expected_text}")
    except Exception as e:
        print(f"pyperclip error: {e}")
    
    # Test non-ASCII detection
    print("\n--- Testing non-ASCII detection ---")
    test_texts = [
        "Hello world",  # ASCII only
        "Héllö wörld",  # Non-ASCII
        "Hello 世界",    # Mixed
        expected_text   # Swedish
    ]
    
    for text in test_texts:
        has_non_ascii = any(ord(char) > 127 for char in text)
        print(f"'{text[:20]}...': has non-ASCII = {has_non_ascii}")

if __name__ == "__main__":
    test_utf8_text() 