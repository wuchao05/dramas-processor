"""Logging utilities and configuration."""

import logging
import sys
from pathlib import Path
from typing import Optional

try:
    from rich.console import Console
    from rich.logging import RichHandler
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


def setup_logging(
    level: str = "INFO",
    log_file: Optional[Path] = None,
    use_rich: bool = True
) -> logging.Logger:
    """Set up logging configuration.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file to write logs to
        use_rich: Use rich formatting if available
        
    Returns:
        Configured logger
    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add console handler
    if use_rich and RICH_AVAILABLE:
        console_handler = RichHandler(
            console=Console(stderr=True),
            show_time=False,
            show_level=False,
            show_path=False,
            markup=True,
            rich_tracebacks=True
        )
        console_handler.setFormatter(
            logging.Formatter(
                fmt="%(message)s",
                datefmt="[%X]"
            )
        )
    else:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(formatter)
    
    console_handler.setLevel(numeric_level)
    root_logger.addHandler(console_handler)
    
    # Add file handler if specified
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        file_handler.setLevel(numeric_level)
        root_logger.addHandler(file_handler)
    
    # Get package logger
    package_logger = logging.getLogger("drama_processor")
    package_logger.setLevel(numeric_level)
    
    return package_logger


class ProgressLogger:
    """Progress logging for long-running operations."""
    
    def __init__(self, logger: logging.Logger, total_items: int, description: str = "Processing"):
        """Initialize progress logger.
        
        Args:
            logger: Logger instance
            total_items: Total number of items to process
            description: Operation description
        """
        self.logger = logger
        self.total_items = total_items
        self.description = description
        self.completed_items = 0
        self.logger.info(f"Starting {description}: {total_items} items")
    
    def update(self, increment: int = 1, message: str = "") -> None:
        """Update progress.
        
        Args:
            increment: Number of items completed
            message: Optional progress message
        """
        self.completed_items += increment
        progress_pct = (self.completed_items / self.total_items) * 100
        
        log_message = f"{self.description}: {self.completed_items}/{self.total_items} ({progress_pct:.1f}%)"
        if message:
            log_message += f" - {message}"
        
        self.logger.info(log_message)
    
    def complete(self, message: str = "Completed") -> None:
        """Mark operation as complete.
        
        Args:
            message: Completion message
        """
        self.completed_items = self.total_items
        self.logger.info(f"{self.description} {message}: {self.total_items} items")


class TimedLogger:
    """Logger with timing information."""
    
    def __init__(self, logger: logging.Logger, operation: str):
        """Initialize timed logger.
        
        Args:
            logger: Logger instance
            operation: Operation name
        """
        self.logger = logger
        self.operation = operation
        self.start_time = None
    
    def __enter__(self):
        """Enter context manager."""
        import time
        self.start_time = time.time()
        self.logger.info(f"Starting {self.operation}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager."""
        import time
        if self.start_time:
            duration = time.time() - self.start_time
            from .time import human_duration
            
            if exc_type is None:
                self.logger.info(f"Completed {self.operation} in {human_duration(duration)}")
            else:
                self.logger.error(f"Failed {self.operation} after {human_duration(duration)}: {exc_val}")
    
    def log_progress(self, message: str) -> None:
        """Log progress message.
        
        Args:
            message: Progress message
        """
        import time
        if self.start_time:
            elapsed = time.time() - self.start_time
            from .time import human_duration
            self.logger.info(f"{self.operation} ({human_duration(elapsed)}): {message}")
        else:
            self.logger.info(f"{self.operation}: {message}")

