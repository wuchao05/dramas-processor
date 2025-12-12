"""Lite CLI 入口。

Lite 版本保留除 Feishu 之外的所有功能：
- process / analyze / config / history（以及隐藏的 legacy run）
- 运行时强制关闭所有 Feishu 相关配置与侧路能力
"""

import logging
import sys
from pathlib import Path
from typing import Optional

import click

# 注意：Lite 入口会被 PyInstaller 作为脚本直接执行，
# 相对导入在该场景下会失效，因此这里使用绝对导入。
from drama_processor.config import ConfigManager, get_default_config
from drama_processor.utils.logging import setup_logging
from drama_processor.cli.commands import (
    analyze_command,
    config_command,
    history_command,
    legacy_run_command,
    process_command,
)


@click.group()
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Configuration file path",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    default="INFO",
    help="Logging level",
)
@click.option(
    "--log-file",
    type=click.Path(path_type=Path),
    help="Log file path",
)
@click.option(
    "--no-rich",
    is_flag=True,
    help="Disable rich formatting",
)
@click.pass_context
def cli(ctx, config: Optional[Path], log_level: str, log_file: Optional[Path], no_rich: bool):
    """Drama Processor Lite - 无 Feishu 版本。"""
    ctx.ensure_object(dict)

    logger = setup_logging(
        level=log_level,
        log_file=log_file,
        use_rich=not no_rich,
    )

    if config is None:
        default_config_paths = [
            Path("configs/lite.yaml"),
            Path("configs/default.yaml"),
            Path("config/default.yaml"),
            Path("default.yaml"),
            Path.cwd() / "configs" / "lite.yaml",
            Path.cwd() / "configs" / "default.yaml",
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

    # Lite 版本强制关闭 Feishu 能力
    if processing_config.enable_feishu_features:
        logger.info("Lite 版本已强制关闭所有 Feishu 相关功能")
    processing_config.enable_feishu_features = False
    processing_config.enable_feishu_notification = False
    processing_config.feishu = None
    if processing_config.feishu_watcher:
        processing_config.feishu_watcher.enabled = False

    ctx.obj["config_manager"] = config_manager
    ctx.obj["config"] = processing_config
    ctx.obj["logger"] = logger


cli.add_command(process_command)
cli.add_command(analyze_command)
cli.add_command(config_command)
cli.add_command(legacy_run_command)
cli.add_command(history_command)


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
