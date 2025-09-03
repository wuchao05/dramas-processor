"""Project and output models."""

from pathlib import Path
from typing import List, Optional, Tuple
from datetime import datetime
from pydantic import BaseModel, Field, validator

from .episode import Episode


class MaterialOutput(BaseModel):
    """Represents a generated material output."""
    
    output_path: Path = Field(description="Output file path")
    drama_name: str = Field(description="Drama name")
    material_index: int = Field(description="Material index")
    start_episode: int = Field(description="Starting episode number")
    start_offset: float = Field(description="Starting offset in seconds")
    total_duration: float = Field(description="Total material duration")
    segments_count: int = Field(description="Number of segments")
    processing_time: float = Field(description="Processing time in seconds")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    has_tail: bool = Field(default=False, description="Has tail video")
# Cover field removed
    file_size: Optional[int] = Field(default=None, description="File size in bytes")
    
    @validator("material_index")
    def validate_material_index(cls, v: int) -> int:
        """Validate material index is positive."""
        if v <= 0:
            raise ValueError("Material index must be positive")
        return v
    
    @validator("start_episode")
    def validate_start_episode(cls, v: int) -> int:
        """Validate start episode is positive."""
        if v <= 0:
            raise ValueError("Start episode must be positive")
        return v
    
    @validator("start_offset")
    def validate_start_offset(cls, v: float) -> float:
        """Validate start offset is non-negative."""
        if v < 0:
            raise ValueError("Start offset must be non-negative")
        return v
    
    @validator("total_duration", "processing_time")
    def validate_positive_duration(cls, v: float) -> float:
        """Validate duration values are positive."""
        if v <= 0:
            raise ValueError("Duration must be positive")
        return v
    
    @validator("segments_count")
    def validate_segments_count(cls, v: int) -> int:
        """Validate segments count is positive."""
        if v <= 0:
            raise ValueError("Segments count must be positive")
        return v


class DramaProject(BaseModel):
    """Represents a drama processing project."""
    
    name: str = Field(description="Drama name")
    source_dir: Path = Field(description="Source directory path")
    episodes: List[Episode] = Field(default_factory=list, description="Episode list")
    output_dir: Optional[Path] = Field(default=None, description="Output directory")
    run_suffix: Optional[str] = Field(default=None, description="Run suffix")
    materials_generated: List[MaterialOutput] = Field(
        default_factory=list, 
        description="Generated materials"
    )
# Cover image field removed
    tail_video: Optional[Path] = Field(default=None, description="Tail video path")
    reference_resolution: Optional[Tuple[int, int]] = Field(
        default=None, 
        description="Reference resolution (width, height)"
    )
    target_fps: Optional[int] = Field(default=None, description="Target FPS")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.now, description="Last update timestamp")
    
    @validator("name")
    def validate_name(cls, v: str) -> str:
        """Validate drama name is not empty."""
        if not v.strip():
            raise ValueError("Drama name cannot be empty")
        return v.strip()
    
    @validator("source_dir")
    def validate_source_dir(cls, v: Path) -> Path:
        """Validate source directory exists."""
        if not v.exists():
            raise ValueError(f"Source directory does not exist: {v}")
        if not v.is_dir():
            raise ValueError(f"Source path is not a directory: {v}")
        return v
    
    @validator("target_fps")
    def validate_target_fps(cls, v: Optional[int]) -> Optional[int]:
        """Validate target FPS is positive if provided."""
        if v is not None and v <= 0:
            raise ValueError("Target FPS must be positive")
        return v
    
    @property
    def total_episodes(self) -> int:
        """Get total number of episodes."""
        return len(self.episodes)
    
    @property
    def total_materials(self) -> int:
        """Get total number of generated materials."""
        return len(self.materials_generated)
    
    @property
    def total_duration(self) -> float:
        """Get total duration of all episodes."""
        return sum(ep.duration or 0 for ep in self.episodes)
    
    @property
    def safe_episodes_count(self) -> int:
        """Get count of safe episodes."""
        return sum(1 for ep in self.episodes if ep.is_safe is True)
    
    @property
    def unsafe_episodes_count(self) -> int:
        """Get count of unsafe episodes."""
        return sum(1 for ep in self.episodes if ep.is_safe is False)
    
    @property
    def analyzed_episodes_count(self) -> int:
        """Get count of analyzed episodes."""
        return sum(1 for ep in self.episodes if ep.is_analyzed)
    
    def add_episode(self, episode: Episode) -> None:
        """Add an episode to the project."""
        self.episodes.append(episode)
        self.updated_at = datetime.now()
    
    def add_material(self, material: MaterialOutput) -> None:
        """Add a generated material to the project."""
        self.materials_generated.append(material)
        self.updated_at = datetime.now()
    
    def get_episode_by_number(self, episode_number: int) -> Optional[Episode]:
        """Get episode by number."""
        for episode in self.episodes:
            if episode.episode_number == episode_number:
                return episode
        return None
    
    def get_safe_episodes(self) -> List[Episode]:
        """Get list of safe episodes."""
        return [ep for ep in self.episodes if ep.is_safe is not False]
    
    def get_unsafe_episodes(self) -> List[Episode]:
        """Get list of unsafe episodes."""
        return [ep for ep in self.episodes if ep.is_safe is True]

