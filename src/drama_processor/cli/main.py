"""Main CLI entry point."""

import logging
import os
import sys
from pathlib import Path
from typing import List, Optional

import click

from ..config import ConfigManager, get_default_config
from ..core.processor import DramaProcessor
from ..utils.logging import setup_logging
from ..utils.license import (
    FEATURE_ALL,
    FEATURE_FEISHU,
    LicenseError,
    get_allowed_features_from_args_and_env,
    get_license_info_from_args_and_env,
    load_and_verify_license,
)
from .commands import process_command, analyze_command, config_command, legacy_run_command, history_command, feishu_command
# AI功能已移除


# import 时先读取 license（参数/环境变量），决定是否注册 feishu 命令
_ALLOWED_FEATURES_AT_IMPORT = get_allowed_features_from_args_and_env(sys.argv)


@click.group()
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Configuration file path"
)
@click.option(
    "--license",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="授权文件路径（可选，用于解锁 Feishu 等高级功能）",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    default="INFO",
    help="Logging level"
)
@click.option(
    "--log-file",
    type=click.Path(path_type=Path),
    help="Log file path"
)
@click.option(
    "--no-rich",
    is_flag=True,
    help="Disable rich formatting"
)
@click.pass_context
def cli(
    ctx,
    config: Optional[Path],
    license: Optional[Path],
    log_level: str,
    log_file: Optional[Path],
    no_rich: bool,
):
    """Drama Processor - Professional video processing tool for drama series."""
    # Ensure context object exists
    ctx.ensure_object(dict)
    
    # Set up logging
    logger = setup_logging(
        level=log_level,
        log_file=log_file,
        use_rich=not no_rich
    )
    
    # Load configuration
    # If no config specified, try to find default config file
    if config is None:
        # Try to find default config file.
        # 约定：
        # - Pro 二进制：优先 pro.yaml（若存在），否则回退 default.yaml
        # - 源码开发态 + DEV_BYPASS：为避免误用 pro.yaml（仅面向发布包），强制优先 default.yaml
        dev_bypass_raw = os.environ.get("DRAMA_PROCESSOR_DEV_BYPASS")
        dev_bypass_enabled = (
            not getattr(sys, "frozen", False)
            and dev_bypass_raw is not None
            and dev_bypass_raw.strip().lower() in {"1", "true", "yes", "y", "on"}
        )

        if dev_bypass_enabled:
            default_config_paths = [
                Path("configs/default.yaml"),
                Path("config/default.yaml"),
                Path("default.yaml"),
                Path.cwd() / "configs" / "default.yaml",
                Path.cwd() / "config" / "default.yaml",
            ]
        else:
            # Pro 版本默认优先使用 configs/pro.yaml（若存在），否则回退 default.yaml
            default_config_paths = [
                Path("configs/pro.yaml"),
                Path("configs/default.yaml"),
                Path("config/pro.yaml"),
                Path("config/default.yaml"),
                Path("pro.yaml"),
                Path("default.yaml"),
                Path.cwd() / "configs" / "pro.yaml",
                Path.cwd() / "configs" / "default.yaml",
                Path.cwd() / "config" / "pro.yaml",
                Path.cwd() / "config" / "default.yaml",
            ]
        
        for config_path in default_config_paths:
            if config_path.exists():
                config = config_path
                break
    
    config_manager = ConfigManager(config)
    try:
        processing_config = config_manager.load()
        logger.info("Configuration loaded successfully")
    except Exception as e:
        logger.warning(f"Failed to load configuration: {e}")
        processing_config = get_default_config()
        logger.info("Using default configuration")

    # License 校验：显式 --license 优先，否则从 argv/env 读取
    license_info = None
    if license is not None:
        try:
            license_info = load_and_verify_license(str(license))
            logger.info("License 校验通过")
        except (LicenseError, Exception) as e:
            logger.warning(f"License 校验失败，将以未授权模式运行：{e}")
            license_info = None
    else:
        license_info = get_license_info_from_args_and_env(sys.argv, logger_=logger)

    ctx.obj["license"] = license_info

    # 未授权 feishu 时，强制关闭所有 feishu 相关配置，避免通过 process 侧路使用
    if not (license_info and license_info.allows(FEATURE_FEISHU)):
        if processing_config.enable_feishu_features:
            logger.warning("未授权 Feishu 功能，已强制关闭 enable_feishu_features")
        processing_config.enable_feishu_features = False
        processing_config.enable_feishu_notification = False
        processing_config.feishu = None
        if processing_config.feishu_watcher:
            processing_config.feishu_watcher.enabled = False
    
    # Store in context
    ctx.obj["config_manager"] = config_manager
    ctx.obj["config"] = processing_config
    ctx.obj["logger"] = logger


# Add subcommands
cli.add_command(process_command)
cli.add_command(analyze_command) 
cli.add_command(config_command)
cli.add_command(legacy_run_command)
cli.add_command(history_command)
if FEATURE_ALL in _ALLOWED_FEATURES_AT_IMPORT or FEATURE_FEISHU in _ALLOWED_FEATURES_AT_IMPORT:
    cli.add_command(feishu_command)

# AI功能已移除


def main():
    """Main entry point."""
    try:
        cli()
    except KeyboardInterrupt:
        click.echo("\nOperation cancelled by user", err=True)
        sys.exit(130)
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception("Unexpected error occurred")
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
