"""
Configuration manager for Voice Typing System.
Handles loading, validation, and access to application settings.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any
import logging

class ConfigManager:
    """Manages application configuration with defaults and user overrides."""
    
    def __init__(self, config_dir: str = None):
        """
        Initialize configuration manager.
        
        Args:
            config_dir: Directory containing configuration files
        """
        self.config_dir = Path(config_dir) if config_dir else Path(__file__).parent.parent / "config"
        self.runtime_dir = Path.home() / ".local" / "share" / "voice-typing-system"
        self.user_config_file = self.runtime_dir / "config.json"
        self.default_config_file = self.config_dir / "default_config.json"
        
        # Ensure runtime directory exists
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        (self.runtime_dir / "logs").mkdir(exist_ok=True)
        (self.runtime_dir / "recordings").mkdir(exist_ok=True)
        
        self.config = self._load_config()
        self._setup_logging()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from default and user files."""
        # Load default config
        with open(self.default_config_file, 'r') as f:
            default_config = json.load(f)
        
        # Load user config if it exists
        user_config = {}
        if self.user_config_file.exists():
            try:
                with open(self.user_config_file, 'r') as f:
                    user_config = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logging.warning(f"Failed to load user config: {e}")
        
        # Merge configurations (user config overrides defaults)
        config = self._merge_configs(default_config, user_config)
        
        # Expand paths
        config = self._expand_paths(config)
        
        return config
    
    def _merge_configs(self, default: Dict, user: Dict) -> Dict:
        """Recursively merge user config into default config."""
        result = default.copy()
        
        for key, value in user.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _expand_paths(self, config: Dict) -> Dict:
        """Expand ~ and relative paths in configuration."""
        def expand_path(value):
            if isinstance(value, str) and value.startswith('~'):
                return str(Path(value).expanduser())
            return value
        
        def expand_dict(d):
            for key, value in d.items():
                if isinstance(value, dict):
                    expand_dict(value)
                elif isinstance(value, str):
                    d[key] = expand_path(value)
        
        expand_dict(config)
        return config
    
    def _setup_logging(self):
        """Setup logging based on configuration."""
        log_config = self.config.get('logging', {})
        log_level = getattr(logging, log_config.get('level', 'INFO'))
        log_file = log_config.get('file', str(self.runtime_dir / "logs" / "app.log"))
        
        # Ensure log directory exists
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by dot-notation key."""
        keys = key.split('.')
        value = self.config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any):
        """Set configuration value by dot-notation key."""
        keys = key.split('.')
        config = self.config
        
        # Navigate to the parent of the target key
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        # Set the value
        config[keys[-1]] = value
    
    def save_user_config(self):
        """Save current configuration to user config file."""
        try:
            with open(self.user_config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            logging.info(f"Configuration saved to {self.user_config_file}")
        except IOError as e:
            logging.error(f"Failed to save configuration: {e}")
    
    def get_recording_directory(self) -> Path:
        """Get the recording directory path."""
        recording_dir = self.get('recording.directory')
        path = Path(recording_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    def get_api_endpoint(self) -> str:
        """Get the API endpoint URL."""
        return self.get('api.endpoint')
    
    def get_audio_settings(self) -> Dict[str, Any]:
        """Get audio recording settings."""
        return self.get('audio', {})
    
    def get_hotkey_combination(self) -> str:
        """Get the hotkey combination."""
        return self.get('hotkey.combination') 