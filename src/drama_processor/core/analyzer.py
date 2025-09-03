"""Video analysis module."""

import logging
from pathlib import Path
from typing import List, Optional

from ..models.episode import Episode
from ..utils.video import probe_video_stream

logger = logging.getLogger(__name__)


class VideoAnalyzer:
    """Video analysis and metadata extraction."""
    
    def __init__(self):
        """Initialize video analyzer."""
        pass
    
    def analyze_episode(self, file_path: Path, episode_number: int) -> Episode:
        """Analyze a single episode file.
        
        Args:
            file_path: Path to episode file
            episode_number: Episode number
            
        Returns:
            Episode object with metadata
            
        Raises:
            RuntimeError: If analysis fails
        """
        logger.info(f"Analyzing episode {episode_number}: {file_path}")
        
        try:
            info = probe_video_stream(file_path)
            
            episode = Episode(
                file_path=file_path,
                episode_number=episode_number,
                duration=info["duration"],
                width=info["w"],
                height=info["h"],
                fps=info["fps"],
                is_safe=True  # Assume safe for now
            )
            
            logger.debug(
                f"Episode {episode_number} analysis: "
                f"{info['w']}x{info['h']} @ {info['fps']:.2f}fps, "
                f"duration: {info['duration']:.2f}s"
            )
            
            return episode
            
        except Exception as e:
            logger.error(f"Failed to analyze episode {episode_number}: {e}")
            raise RuntimeError(f"Episode analysis failed: {e}")
    
    def analyze_episodes(self, episode_files: List[Path]) -> List[Episode]:
        """Analyze multiple episode files.
        
        Args:
            episode_files: List of episode file paths
            
        Returns:
            List of analyzed episodes
        """
        episodes = []
        
        for i, file_path in enumerate(episode_files, 1):
            try:
                episode = self.analyze_episode(file_path, i)
                episodes.append(episode)
            except RuntimeError as e:
                logger.warning(f"Skipping episode {i}: {e}")
                continue
        
        logger.info(f"Successfully analyzed {len(episodes)}/{len(episode_files)} episodes")
        return episodes
    
    def get_common_resolution(self, episodes: List[Episode]) -> tuple[int, int]:
        """Get the most common resolution from episodes.
        
        Args:
            episodes: List of episodes
            
        Returns:
            Most common (width, height) resolution
            
        Raises:
            ValueError: If no valid resolutions found
        """
        resolutions = []
        
        for episode in episodes:
            if episode.width and episode.height:
                # Ensure even dimensions
                width = episode.width if episode.width % 2 == 0 else episode.width - 1
                height = episode.height if episode.height % 2 == 0 else episode.height - 1
                resolutions.append((width, height))
        
        if not resolutions:
            raise ValueError("No valid resolutions found in episodes")
        
        # Find most common resolution
        from collections import Counter
        most_common = Counter(resolutions).most_common(1)[0][0]
        
        logger.info(f"Selected common resolution: {most_common[0]}x{most_common[1]}")
        return most_common
    
    def choose_output_fps(self, episodes: List[Episode], target_fps: int, smart_fps: bool = True) -> int:
        """Choose output FPS based on source material.
        
        Args:
            episodes: List of episodes
            target_fps: Target FPS from configuration
            smart_fps: Enable smart FPS adaptation
            
        Returns:
            Chosen output FPS
        """
        if not smart_fps:
            return target_fps
        
        # Find first episode with valid FPS
        source_fps = None
        for episode in episodes:
            if episode.fps and episode.fps > 0:
                source_fps = episode.fps
                break
        
        if source_fps is None:
            logger.warning("No valid source FPS found, using target FPS")
            return target_fps
        
        # Smart FPS logic
        if source_fps < 40:
            output_fps = int(round(source_fps))
        else:
            output_fps = 45
        
        logger.info(f"Smart FPS: source ≈ {source_fps:.2f} -> output {output_fps}")
        return output_fps

