"""Video segment building module."""

import logging
from typing import List, Optional, Dict, Tuple

from ..models.episode import Episode, EpisodeSegment

from ..utils.video import probe_duration

logger = logging.getLogger(__name__)


class SegmentBuilder:
    """Builds video segments from episodes."""
    
    def __init__(self):
        """Initialize segment builder."""
        pass
    
    def build_segments_at_episode_boundaries(
        self,
        episodes: List[Episode],
        start_episode_idx: int,
        start_offset: float,
        min_duration: float,
        max_duration: float
    ) -> List[EpisodeSegment]:
        """Build segments aligned to episode boundaries.
        
        Args:
            episodes: List of available episodes
            start_episode_idx: Starting episode index
            start_offset: Starting offset in seconds
            min_duration: Minimum total duration
            max_duration: Maximum total duration
            
        Returns:
            List of episode segments
        """
        logger.debug(
            f"Building segments: start_ep={start_episode_idx}, "
            f"offset={start_offset}, duration={min_duration}-{max_duration}s"
        )
        
        choices = []
        total_duration = 0.0
        
        for i in range(start_episode_idx, len(episodes)):
            episode = episodes[i]
            
            # Get episode duration
            try:
                duration = episode.duration
                if duration is None:
                    duration = probe_duration(episode.file_path)
            except Exception as e:
                logger.warning(f"Cannot get duration for episode {episode.episode_number}: {e}")
                continue
            
            # Calculate segment timing
            seg_start = start_offset if i == start_episode_idx else 0.0
            seg_end = duration
            take_duration = max(0.0, seg_end - seg_start)
            
            if take_duration <= 0:
                continue
            
            total_duration += take_duration
            
            choices.append({
                "episode_idx": i,
                "episode": episode,
                "start": seg_start,
                "end": seg_end,
                "cumulative": total_duration,
                "apply_blur": False
            })
            
            # Stop if we've reached maximum duration
            if total_duration >= max_duration:
                break
        
        if not choices:
            logger.warning("No valid segments found")
            return []
        
        # Find optimal cutoff point
        target_duration = (min_duration + max_duration) / 2.0
        
        # Find segments within acceptable range
        valid_choices = [
            (idx, choice) for idx, choice in enumerate(choices)
            if min_duration <= choice["cumulative"] <= max_duration
        ]
        
        if valid_choices:
            # Choose closest to target duration
            best_idx, _ = min(
                valid_choices,
                key=lambda x: abs(x[1]["cumulative"] - target_duration)
            )
        else:
            # Choose closest to target duration from all choices
            best_idx = min(
                range(len(choices)),
                key=lambda idx: abs(choices[idx]["cumulative"] - target_duration)
            )
        
        # Build final segment list
        segments = []
        selected_choices = choices[:best_idx + 1]
        
        for choice in selected_choices:
            segment = EpisodeSegment(
                source_path=choice["episode"].file_path,
                start_time=choice["start"],
                end_time=choice["end"],
                apply_blur=choice["apply_blur"]
            )
            segments.append(segment)
        
        total_final_duration = sum(seg.duration for seg in segments)
        logger.info(
            f"Built {len(segments)} segments, total duration: {total_final_duration:.2f}s"
        )
        
        return segments
    
    def validate_segments(self, segments: List[EpisodeSegment]) -> bool:
        """Validate segment list.
        
        Args:
            segments: List of segments to validate
            
        Returns:
            True if segments are valid
        """
        if not segments:
            return False
        
        for i, segment in enumerate(segments):
            # Check file exists
            if not segment.source_path.exists():
                logger.error(f"Segment {i}: source file not found: {segment.source_path}")
                return False
            
            # Check timing
            if segment.start_time < 0 or segment.end_time <= segment.start_time:
                logger.error(f"Segment {i}: invalid timing: {segment.start_time}-{segment.end_time}")
                return False
        
        return True

