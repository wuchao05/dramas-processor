"""Configuration loading and saving."""

import logging
import yaml
from pathlib import Path
from typing import Dict, Any, Union, Optional

from ..models.config import ProcessingConfig
from .defaults import get_default_config

logger = logging.getLogger(__name__)


def _deep_update(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """递归合并字典，override 中的值覆盖 base 中的值。
    
    Args:
        base: 基础字典
        override: 覆盖字典
        
    Returns:
        合并后的字典
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_update(result[key], value)
        else:
            result[key] = value
    return result


def _load_user_config(config_path: Path, active_user: str) -> Optional[Dict[str, Any]]:
    """加载用户专属配置文件。
    
    Args:
        config_path: 主配置文件路径
        active_user: 用户名（如 xh, xl, xx）
        
    Returns:
        用户配置字典，如果文件不存在则返回 None
    """
    # 用户配置文件路径：configs/users/{active_user}.yaml
    users_dir = config_path.parent / "users"
    user_config_path = users_dir / f"{active_user}.yaml"
    
    if not user_config_path.exists():
        logger.warning(f"用户配置文件不存在: {user_config_path}")
        return None
    
    try:
        with open(user_config_path, 'r', encoding='utf-8') as f:
            user_data = yaml.safe_load(f)
        
        if user_data is None:
            return {}
        
        logger.info(f"已加载用户配置: {active_user} ({user_config_path})")
        return user_data
        
    except yaml.YAMLError as e:
        logger.error(f"用户配置文件格式错误: {e}")
        return None
    except Exception as e:
        logger.error(f"加载用户配置失败: {e}")
        return None


def load_config(config_path: Union[str, Path]) -> ProcessingConfig:
    """Load configuration from file with user config merging.
    
    加载主配置文件，如果指定了 active_user，则自动加载并合并用户配置。
    用户配置文件位于 configs/users/{active_user}.yaml
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Loaded configuration with user overrides applied
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config file is invalid
    """
    config_path = Path(config_path)
    
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    try:
        # 1. 加载主配置文件
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        
        if config_data is None:
            config_data = {}
        
        # 2. 检查是否有 active_user 配置
        active_user = config_data.get('active_user')
        
        if active_user:
            # 3. 加载用户配置
            user_config = _load_user_config(config_path, active_user)
            
            if user_config:
                # 4. 合并配置（用户配置覆盖主配置）
                config_data = _deep_update(config_data, user_config)
                logger.debug(f"用户配置已合并: {active_user}")
        
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
    config_dict = _deep_update(config_dict, override_data)
    return ProcessingConfig(**config_dict)
