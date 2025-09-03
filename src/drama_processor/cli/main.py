"""Main CLI entry point."""

import logging
import sys
from pathlib import Path
from typing import List, Optional

import click

from ..config import ConfigManager, get_default_config
from ..core.processor import DramaProcessor
from ..utils.logging import setup_logging
from .commands import process_command, analyze_command, config_command, legacy_run_command, history_command


@click.group()
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Configuration file path"
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
def cli(ctx, config: Optional[Path], log_level: str, log_file: Optional[Path], no_rich: bool):
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
    config_manager = ConfigManager(config)
    try:
        processing_config = config_manager.load()
        logger.info("Configuration loaded successfully")
    except Exception as e:
        logger.warning(f"Failed to load configuration: {e}")
        processing_config = get_default_config()
        logger.info("Using default configuration")
    
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

