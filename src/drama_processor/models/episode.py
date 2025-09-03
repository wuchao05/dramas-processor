"""Episode and segment models."""

from pathlib import Path
from typing import Optional, List
from pydantic import BaseModel, Field, validator


class EpisodeSegment(BaseModel):
    """Represents a segment of an episode."""
    
    source_path: Path = Field(description="Source video file path")
    start_time: float = Field(description="Start time in seconds")
    end_time: float = Field(description="End time in seconds") 
    apply_blur: bool = Field(default=False, description="Apply blur filter")
    
    @validator("start_time", "end_time")
    def validate_times(cls, v: float) -> float:
        """Validate times are non-negative."""
        if v < 0:
            raise ValueError("Time values must be non-negative")
        return v
    
    @validator("end_time")
    def validate_end_after_start(cls, v: float, values: dict) -> float:
        """Validate end time is after start time."""
        start = values.get("start_time", 0)
        if v <= start:
            raise ValueError("End time must be after start time")
        return v
    
    @property
    def duration(self) -> float:
        """Get segment duration."""
        return self.end_time - self.start_time


class Episode(BaseModel):
    """Represents a drama episode."""
    
    file_path: Path = Field(description="Episode file path")
    episode_number: int = Field(description="Episode number")
    duration: Optional[float] = Field(default=None, description="Episode duration in seconds")
    width: Optional[int] = Field(default=None, description="Video width")
    height: Optional[int] = Field(default=None, description="Video height")
    fps: Optional[float] = Field(default=None, description="Video FPS")
    is_safe: Optional[bool] = Field(default=None, description="Whether episode is safe to process")

    
    @validator("episode_number")
    def validate_episode_number(cls, v: int) -> int:
        """Validate episode number is positive."""
        if v <= 0:
            raise ValueError("Episode number must be positive")
        return v
    
    @validator("duration")
    def validate_duration(cls, v: Optional[float]) -> Optional[float]:
        """Validate duration is positive if provided."""
        if v is not None and v <= 0:
            raise ValueError("Duration must be positive")
        return v
    
    @validator("width", "height")
    def validate_dimensions(cls, v: Optional[int]) -> Optional[int]:
        """Validate dimensions are positive if provided."""
        if v is not None and v <= 0:
            raise ValueError("Dimensions must be positive")
        return v
    
    @validator("fps")
    def validate_fps(cls, v: Optional[float]) -> Optional[float]:
        """Validate FPS is positive if provided."""
        if v is not None and v <= 0:
            raise ValueError("FPS must be positive")
        return v
    
    @property
    def is_analyzed(self) -> bool:
        """Check if episode has been analyzed."""
        return all([
            self.duration is not None,
            self.width is not None,
            self.height is not None,
            self.fps is not None
        ])
    


