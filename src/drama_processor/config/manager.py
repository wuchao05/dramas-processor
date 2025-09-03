"""Configuration manager."""

from pathlib import Path
from typing import Optional, Dict, Any

from ..models.config import ProcessingConfig
from .loader import load_config_with_fallback, save_config, merge_configs
from .defaults import get_default_config


class ConfigManager:
    """Configuration manager for drama processor."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize config manager.
        
        Args:
            config_path: Optional path to configuration file
        """
        self.config_path = config_path
        self._config: Optional[ProcessingConfig] = None
    
    @property
    def config(self) -> ProcessingConfig:
        """Get current configuration."""
        if self._config is None:
            self._config = self.load()
        return self._config
    
    def load(self, config_path: Optional[Path] = None) -> ProcessingConfig:
        """Load configuration.
        
        Args:
            config_path: Optional path to configuration file
            
        Returns:
            Loaded configuration
        """
        path = config_path or self.config_path
        self._config = load_config_with_fallback(path)
        return self._config
    
    def save(self, config_path: Optional[Path] = None) -> None:
        """Save current configuration.
        
        Args:
            config_path: Optional path to save configuration
            
        Raises:
            ValueError: If no configuration is loaded
        """
        if self._config is None:
            raise ValueError("No configuration loaded")
        
        path = config_path or self.config_path
        if path is None:
            raise ValueError("No configuration path specified")
        
        save_config(self._config, path)
    
    def update(self, **kwargs: Any) -> None:
        """Update configuration parameters.
        
        Args:
            **kwargs: Configuration parameters to update
        """
        if self._config is None:
            self._config = get_default_config()
        
        self._config = merge_configs(self._config, kwargs)
    
    def reset(self) -> None:
        """Reset configuration to defaults."""
        self._config = get_default_config()
    
    def get_config_dict(self) -> Dict[str, Any]:
        """Get configuration as dictionary.
        
        Returns:
            Configuration dictionary
        """
        return self.config.dict()
    
    def validate_config(self) -> bool:
        """Validate current configuration.
        
        Returns:
            True if configuration is valid
        """
        try:
            self.config.dict()
            return True
        except Exception:
            return False

