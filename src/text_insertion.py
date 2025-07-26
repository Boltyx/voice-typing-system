"""
Text insertion module for Voice Typing System.
Handles pasting transcribed text into focused input fields.
"""

import pyautogui
import pyperclip
import time
import logging
from typing import Optional

class TextInsertion:
    """Handles text insertion into focused input fields."""
    
    def __init__(self):
        """Initialize text insertion manager."""
        # Configure pyautogui for safety
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.1
    
    def insert_text(self, text: str) -> Optional[str]:
        """
        Insert text into the currently focused input field.
        
        Args:
            text: Text to insert
            
        Returns:
            The name of the method used if successful, otherwise None.
        """
        try:
            logging.info(f"Attempting to insert text: {len(text)} characters")
            
            # Method 1: Try direct typing (most reliable)
            method = self._type_text(text)
            if method:
                logging.info(f"Text inserted successfully via {method}")
                return method
            
            # Method 2: Try clipboard paste
            method = self._paste_text(text)
            if method:
                logging.info(f"Text inserted successfully via {method}")
                return method
            
            # Method 3: Try hotkey paste
            method = self._hotkey_paste(text)
            if method:
                logging.info(f"Text inserted successfully via {method}")
                return method
            
            logging.warning("All text insertion methods failed")
            return None
            
        except Exception as e:
            logging.error(f"Error during text insertion: {e}")
            return None
    
    def _type_text(self, text: str) -> Optional[str]:
        """
        Type text directly into focused field.
        
        Args:
            text: Text to type
            
        Returns:
            The method name if successful, otherwise None.
        """
        try:
            # Small delay to ensure focus
            time.sleep(0.1)
            
            # For UTF-8 text, use clipboard paste instead of direct typing
            # as pyautogui.write() may not handle non-ASCII characters well
            if any(ord(char) > 127 for char in text):
                # Text contains non-ASCII characters, use clipboard
                pyperclip.copy(text)
                pyautogui.hotkey('ctrl', 'v')
                return "clipboard_paste_utf8"
            else:
                pyautogui.write(text)
                return "direct_typing"
            
        except Exception as e:
            logging.debug(f"Direct typing failed: {e}")
            return None
    
    def _paste_text(self, text: str) -> Optional[str]:
        """
        Paste text using clipboard.
        
        Args:
            text: Text to paste
            
        Returns:
            The method name if successful, otherwise None.
        """
        try:
            # Save current clipboard
            original_clipboard = pyperclip.paste()
            
            # Set new text to clipboard (properly handles UTF-8)
            pyperclip.copy(text)
            
            # Paste using Ctrl+V
            pyautogui.hotkey('ctrl', 'v')
            
            # Restore original clipboard
            pyperclip.copy(original_clipboard)
            
            return "clipboard_paste_restored"
            
        except Exception as e:
            logging.debug(f"Clipboard paste failed: {e}")
            return None
    
    def _hotkey_paste(self, text: str) -> Optional[str]:
        """
        Paste text using Ctrl+V after setting clipboard.
        
        Args:
            text: Text to paste
            
        Returns:
            The method name if successful, otherwise None.
        """
        try:
            # Set clipboard content (properly handles UTF-8)
            pyperclip.copy(text)
            
            # Use Ctrl+V to paste
            pyautogui.hotkey('ctrl', 'v')
            
            return "hotkey_paste"
            
        except Exception as e:
            logging.debug(f"Hotkey paste failed: {e}")
            return None
    
    def get_focused_window_info(self) -> Optional[dict]:
        """
        Get information about the currently focused window.
        
        Returns:
            Window information or None if failed
        """
        try:
            # This is a basic implementation
            # In a real scenario, you might want to use xdotool or similar
            mouse_pos = pyautogui.position()
            return {
                'mouse_x': mouse_pos.x,
                'mouse_y': mouse_pos.y,
                'timestamp': time.time()
            }
        except Exception as e:
            logging.debug(f"Failed to get window info: {e}")
            return None
    
    def is_input_field_focused(self) -> bool:
        """
        Check if an input field is currently focused.
        This is a basic check - in practice, it's hard to determine reliably.
        
        Returns:
            True if likely focused on input field
        """
        try:
            # This is a simplified check
            # In practice, you might want to use more sophisticated methods
            return True  # Assume input field is focused
        except Exception as e:
            logging.debug(f"Failed to check input field focus: {e}")
            return False 