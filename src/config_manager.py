"""
Configuration manager for Voice Typing System.
Handles loading, validation, and access to application settings.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any
import logging
from dotenv import load_dotenv

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
        """Load configuration from default, user, and environment files."""
        # Load .env file from project root. This will set environment variables.
        # It's safe to call this even if the file doesn't exist.
        dotenv_path = self.config_dir.parent / '.env'
        load_dotenv(dotenv_path=dotenv_path)
        logging.info(f"Attempting to load .env file from: {dotenv_path}")

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
        
        # Layer environment variables on top (highest priority)
        self._override_with_env_vars(config)

        # Expand paths
        config = self._expand_paths(config)
        
        return config
    
    def _override_with_env_vars(self, config: Dict):
        """Overrides config values with environment variables if they exist."""
        # Map env vars to config paths
        env_map = {
            "VTS_USE_EXTERNAL_SERVICE": "api.use_external_service",
            "VTS_INTERNAL_HOST": "api.internal_service.host",
            "VTS_INTERNAL_PORT": "api.internal_service.port",
            "VTS_EXTERNAL_HOST": "api.external_service.host",
            "VTS_EXTERNAL_USERNAME": "api.external_service.username",
            "VTS_EXTERNAL_PASSWORD": "api.external_service.password",
        }
        
        for env_var, config_path in env_map.items():
            value = os.getenv(env_var)
            if value is not None:
                logging.info(f"Overriding config with environment variable: {env_var}")
                
                # Special handling for boolean flags
                if env_var == "VTS_USE_EXTERNAL_SERVICE":
                    value = value.lower() in ('true', '1', 't', 'yes')
                elif "PORT" in env_var and value.isdigit():
                    value = int(value)

                # Dive into the config dict to set the value
                keys = config_path.split('.')
                d = config
                for key in keys[:-1]:
                    d = d.setdefault(key, {})
                d[keys[-1]] = value

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