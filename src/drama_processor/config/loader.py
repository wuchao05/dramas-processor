"""Configuration loading and saving."""

import yaml
from pathlib import Path
from typing import Dict, Any, Union

from ..models.config import ProcessingConfig
from .defaults import get_default_config


def load_config(config_path: Union[str, Path]) -> ProcessingConfig:
    """Load configuration from file.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Loaded configuration
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config file is invalid
    """
    config_path = Path(config_path)
    
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        
        if config_data is None:
            config_data = {}
        
        return ProcessingConfig(**config_data)
        
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML configuration: {e}")
    except Exception as e:
        raise ValueError(f"Failed to load configuration: {e}")


def save_config(config: ProcessingConfig, config_path: Union[str, Path]) -> None:
    """Save configuration to file.
    
    Args:
        config: Configuration to save
        config_path: Path to save configuration
        
    Raises:
        OSError: If unable to write file
    """
    config_path = Path(config_path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        config_dict = config.dict()
        
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(
                config_dict,
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=True
            )
            
    except Exception as e:
        raise OSError(f"Failed to save configuration: {e}")


def load_config_with_fallback(config_path: Union[str, Path, None]) -> ProcessingConfig:
    """Load configuration with fallback to defaults.
    
    Args:
        config_path: Path to configuration file (optional)
        
    Returns:
        Loaded or default configuration
    """
    if config_path is None:
        return get_default_config()
    
    try:
        return load_config(config_path)
    except (FileNotFoundError, ValueError):
        return get_default_config()


def merge_configs(base_config: ProcessingConfig, override_data: Dict[str, Any]) -> ProcessingConfig:
    """Merge configuration with override data.
    
    Args:
        base_config: Base configuration
        override_data: Override data
        
    Returns:
        Merged configuration
    """
    config_dict = base_config.dict()
    
    def deep_update(d: Dict[str, Any], u: Dict[str, Any]) -> Dict[str, Any]:
        """Deep update dictionary."""
        for k, v in u.items():
            if isinstance(v, dict):
                d[k] = deep_update(d.get(k, {}), v)
            else:
                d[k] = v
        return d
    
    deep_update(config_dict, override_data)
    return ProcessingConfig(**config_dict)

