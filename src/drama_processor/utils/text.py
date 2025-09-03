"""Text utility functions."""

from pathlib import Path


def to_vertical(text: str) -> str:
    """Convert text to vertical layout.
    
    Args:
        text: Input text
        
    Returns:
        Text with vertical layout (newlines between characters)
    """
    if "\n" in text:
        return text
    return "\n".join(list(text))


def write_text_file(file_path: Path, text: str) -> None:
    """Write text to file.
    
    Args:
        file_path: Output file path
        text: Text content to write
        
    Raises:
        OSError: If file cannot be written
    """
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(text)

