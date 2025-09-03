"""Time utility functions."""


def human_duration(seconds: float) -> str:
    """Convert seconds to human-readable duration.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Human-readable duration string
    """
    try:
        seconds = float(seconds)
    except (ValueError, TypeError):
        return str(seconds)
    
    if seconds >= 60:
        return f"{seconds/60:.2f} 分钟"
    return f"{seconds:.2f} 秒"

