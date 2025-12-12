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
from drama_processor.utils.fingerprint import get_machine_fingerprint
from drama_processor.utils.logging import setup_logging
from drama_processor.utils.license import LicenseError, get_license_info_from_args_and_env, load_and_verify_license
from drama_processor.cli.commands import (
    analyze_command,
    config_command,
    history_command,
    legacy_run_command,
    process_command,
)


@click.group(invoke_without_command=True)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Configuration file path",
)
@click.option(
    "--license",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="授权文件路径（发布包运行必填；也可放在二进制同目录并命名为 license.json 自动识别）",
)
@click.option(
    "--print-fingerprint",
    is_flag=True,
    help="打印本机指纹（用于签发 license），打印后退出",
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
def cli(
    ctx,
    config: Optional[Path],
    license: Optional[Path],
    print_fingerprint: bool,
    log_level: str,
    log_file: Optional[Path],
    no_rich: bool,
):
    """Drama Processor Lite - 无 Feishu 版本。"""
    ctx.ensure_object(dict)

    logger = setup_logging(
        level=log_level,
        log_file=log_file,
        use_rich=not no_rich,
    )

    if print_fingerprint:
        click.echo(get_machine_fingerprint())
        ctx.exit(0)

    # 未传子命令时直接显示帮助，避免报 Missing command
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        ctx.exit(0)

    # 二进制发布包强制要求 license（机器绑定）
    license_info = None
    if license is not None:
        try:
            license_info = load_and_verify_license(str(license))
            logger.info("License 校验通过")
        except (LicenseError, Exception) as e:
            click.echo(f"❌ License 校验失败：{e}", err=True)
            sys.exit(1)
    else:
        license_info = get_license_info_from_args_and_env(sys.argv, logger_=logger)
        if getattr(sys, "frozen", False) and license_info is None:
            click.echo(
                "❌ 缺少 license：发布包运行需要机器绑定授权文件（可用 --license 指定，或放置 license.json 到二进制同目录）",
                err=True,
            )
            sys.exit(1)

    ctx.obj["license"] = license_info

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
