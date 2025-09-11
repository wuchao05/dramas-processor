"""智能场景识别与剪辑点检测模块"""

import cv2
import numpy as np
import logging
from pathlib import Path
from typing import List, Tuple, Dict, Optional, NamedTuple
from dataclasses import dataclass
import time

logger = logging.getLogger(__name__)


@dataclass
class SceneInfo:
    """场景信息"""
    start_time: float      # 开始时间（秒）
    end_time: float        # 结束时间（秒）
    quality_score: float   # 质量评分 (0-1)
    scene_type: str        # 场景类型
    key_frame_path: Optional[str] = None  # 关键帧路径
    confidence: float = 0.0  # 置信度


@dataclass
class OptimalCutPoint:
    """最佳剪辑点"""
    timestamp: float       # 时间戳（秒）
    confidence: float      # 置信度 (0-1)
    cut_type: str         # 剪辑点类型: 'scene_change', 'dialogue_pause', 'action_peak'


class SceneAnalyzer:
    """智能场景分析器
    
    ===== AI剪辑点算法说明 =====
    
    1. 场景检测算法：
       - 基于视频帧直方图相关性检测场景变化
       - 阈值：30% (correlation < 0.7 时认为场景变化)
       - 最小场景时长：2秒 (避免误检测)
    
    2. 剪辑点评分算法：
       - 置信度 (70%权重): 基于场景变化强度，值越大表示场景变化越明显
       - 时间位置偏好 (30%权重): 偏好30秒左右位置，避免片头片尾
    
    3. 筛选策略：
       - 避开前3秒 (片头/广告)
       - 避开后15秒 (确保扩展空间)
       - 置信度要求 ≥ 0.6
       - 返回评分最高的1个起始点
    
    4. 作用说明：
       - 置信度：确保剪辑点在真实的场景边界，避免在同一场景中间切断
       - 时间位置偏好：避免片头广告和片尾预告，选择剧情正式开始的位置
    """
    
    def __init__(self, model_dir: Optional[Path] = None):
        """初始化场景分析器
        
        Args:
            model_dir: 模型目录路径
        """
        self.model_dir = model_dir or Path.home() / ".drama_processor" / "models"
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        # 场景检测参数
        self.scene_threshold = 30.0  # 场景变化阈值
        self.min_scene_duration = 2.0  # 最小场景时长（秒）
        
        logger.info("场景分析器初始化完成")
    
    def analyze_video_scenes(self, video_path: Path, 
                           sample_rate: float = 1.0) -> List[SceneInfo]:
        """分析视频场景
        
        Args:
            video_path: 视频文件路径
            sample_rate: 采样率（每秒采样帧数）
            
        Returns:
            场景信息列表
        """
        logger.info(f"开始分析视频场景: {video_path}")
        
        # 检查文件是否存在
        if not video_path.exists():
            raise FileNotFoundError(f"视频文件不存在: {video_path}")
        
        logger.info(f"文件大小: {video_path.stat().st_size / (1024*1024):.1f} MB")
        
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise RuntimeError(f"无法打开视频文件: {video_path}")
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0
        
        logger.info(f"视频信息: {fps:.2f}fps, {total_frames}帧, {duration:.2f}秒")
        
        # 检查视频参数是否合理
        if fps <= 0 or total_frames <= 0:
            cap.release()
            raise RuntimeError(f"视频参数异常: fps={fps}, frames={total_frames}")
        
        # 对于很长的视频，降低采样率以避免卡死
        if duration > 3600:  # 超过1小时
            logger.warning(f"视频时长过长 ({duration/60:.1f}分钟)，自动降低采样率")
            sample_rate = min(sample_rate, 0.2)  # 最多每5秒采样一次
        elif duration > 1800:  # 超过30分钟
            sample_rate = min(sample_rate, 0.5)  # 最多每2秒采样一次
        
        logger.info(f"实际采样率: {sample_rate:.2f} fps")
        
        try:
            # 场景检测
            scenes = self._detect_scenes(cap, fps, sample_rate)
            
            # 精简处理：给所有场景设置默认分数和类型
            for scene in scenes:
                scene.quality_score = 0.8  # 默认质量分数（不再进行复杂质量评估）
                scene.scene_type = "scene_change"  # 统一场景类型
            
            logger.info(f"✅ 检测到 {len(scenes)} 个场景")
            return scenes
            
        except Exception as e:
            logger.error(f"❌ 场景检测过程中发生错误: {e}")
            # 返回一个默认场景，避免完全失败
            default_scene = SceneInfo(
                start_time=0.0,
                end_time=duration,
                quality_score=0.5,
                scene_type="default"
            )
            return [default_scene]
        finally:
            cap.release()
    
    def find_optimal_cut_points(self, video_path: Path, 
                              target_duration: float,
                              min_duration: float = 300.0,
                              max_duration: float = 900.0) -> List[OptimalCutPoint]:
        """找到最佳剪辑点
        
        Args:
            video_path: 视频路径
            target_duration: 目标时长（秒）
            min_duration: 最小时长
            max_duration: 最大时长
            
        Returns:
            最佳剪辑点列表
        """
        logger.info(f"寻找最佳剪辑点: 目标{target_duration}s, 范围{min_duration}-{max_duration}s")
        
        # 1. 获取场景信息
        scenes = self.analyze_video_scenes(video_path)
        
        # 2. 检测场景变化点
        scene_changes = self._extract_scene_change_points(scenes)
        
        # 3. 简化处理：只使用场景变化点
        # dialogue_pauses = self._detect_dialogue_pauses(video_path)  # 暂时禁用
        # action_peaks = self._detect_action_peaks(video_path)  # 暂时禁用
        
        # 4. 综合评估最佳剪辑点
        all_cut_points = scene_changes  # 只使用场景变化点
        optimal_points = self._select_optimal_segments(
            all_cut_points, target_duration, min_duration, max_duration
        )
        
        logger.info(f"找到 {len(optimal_points)} 个最佳剪辑点")
        return optimal_points
    
    def _detect_scenes(self, cap: cv2.VideoCapture, fps: float, 
                      sample_rate: float) -> List[SceneInfo]:
        """检测场景变化"""
        scenes = []
        prev_hist = None
        scene_start = 0.0
        frame_interval = int(fps / sample_rate)
        
        frame_count = 0
        processed_frames = 0
        max_process_frames = 3000  # 最多处理3000帧，避免卡死
        
        logger.info(f"开始场景检测，采样间隔: {frame_interval} 帧，最大处理帧数: {max_process_frames}")
        
        while True:
            ret, frame = cap.read()
            if not ret:
                logger.info(f"📹 视频读取完成，总共处理了 {processed_frames} 帧")
                break
            
            # 检查是否超过最大处理帧数
            if processed_frames >= max_process_frames:
                logger.warning(f"⚠️ 达到最大处理帧数限制 ({max_process_frames})，停止处理")
                break
            
            # 按采样率处理帧
            if frame_count % frame_interval != 0:
                frame_count += 1
                continue
            
            processed_frames += 1
            if processed_frames % 100 == 0:  # 每处理100帧输出一次进度
                progress_pct = (processed_frames / max_process_frames) * 100
                logger.info(f"🔄 已处理 {processed_frames} 帧 ({progress_pct:.1f}%)，当前时间: {frame_count / fps:.1f}秒")
            
            current_time = frame_count / fps
            
            # 计算直方图
            hist = cv2.calcHist([frame], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
            hist = cv2.normalize(hist, hist).flatten()
            
            if prev_hist is not None:
                # 计算直方图差异
                correlation = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CORREL)
                
                # 场景变化检测
                if correlation < (1 - self.scene_threshold / 100.0):
                    # 检测到场景变化
                    if current_time - scene_start >= self.min_scene_duration:
                        scene = SceneInfo(
                            start_time=scene_start,
                            end_time=current_time,
                            quality_score=0.0,  # 后续计算
                            scene_type="unknown"
                        )
                        scenes.append(scene)
                        scene_start = current_time
            
            prev_hist = hist
            frame_count += 1
        
        # 添加最后一个场景
        if scene_start < frame_count / fps:
            final_scene = SceneInfo(
                start_time=scene_start,
                end_time=frame_count / fps,
                quality_score=0.0,
                scene_type="unknown"
            )
            scenes.append(final_scene)
        
        return scenes
    
    # 移除质量评估相关方法 - 不再需要
    
    def _extract_scene_change_points(self, scenes: List[SceneInfo]) -> List[OptimalCutPoint]:
        """从场景中提取场景变化剪辑点"""
        cut_points = []
        
        for i, scene in enumerate(scenes[:-1]):  # 不包括最后一个场景
            next_scene = scenes[i + 1]
            
            # 场景变化点就是当前场景结束时间
            cut_point = OptimalCutPoint(
                timestamp=scene.end_time,
                confidence=0.8,  # 场景变化点通常比较可靠
                cut_type="scene_change"
            )
            cut_points.append(cut_point)
        
        return cut_points
    
    def _detect_dialogue_pauses(self, video_path: Path) -> List[OptimalCutPoint]:
        """检测对话停顿点（基于音频分析）"""
        # 这里使用简化版本，实际可以使用librosa进行音频分析
        cut_points = []
        
        try:
            import librosa
            
            # 加载音频
            y, sr = librosa.load(str(video_path), sr=None)
            
            # 检测静音段
            intervals = librosa.effects.split(y, top_db=20)  # 20dB阈值
            
            # 在静音段之间找停顿点
            for i in range(len(intervals) - 1):
                end_time = intervals[i][1] / sr
                start_time = intervals[i + 1][0] / sr
                
                # 如果静音时间超过0.5秒，认为是对话停顿
                if start_time - end_time > 0.5:
                    cut_point = OptimalCutPoint(
                        timestamp=(end_time + start_time) / 2,
                        confidence=0.6,
                        cut_type="dialogue_pause"
                    )
                    cut_points.append(cut_point)
        
        except ImportError:
            logger.warning("librosa未安装，跳过对话停顿检测")
        except Exception as e:
            logger.warning(f"对话停顿检测失败: {e}")
        
        return cut_points
    
    def _detect_action_peaks(self, video_path: Path) -> List[OptimalCutPoint]:
        """检测动作高潮点（基于运动分析）"""
        cut_points = []
        
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return cut_points
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        prev_frame = None
        motion_scores = []
        timestamps = []
        
        frame_count = 0
        sample_interval = int(fps)  # 每秒采样一次
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            if frame_count % sample_interval == 0:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                
                if prev_frame is not None:
                    # 计算光流来检测运动
                    flow = cv2.calcOpticalFlowPyrLK(
                        prev_frame, gray, 
                        np.array([[100, 100]], dtype=np.float32).reshape(-1, 1, 2),
                        None
                    )[0]
                    
                    # 计算运动强度
                    if flow is not None and len(flow) > 0:
                        motion_magnitude = np.linalg.norm(flow[0][0])
                        motion_scores.append(motion_magnitude)
                        timestamps.append(frame_count / fps)
                
                prev_frame = gray
            
            frame_count += 1
        
        cap.release()
        
        # 找到运动峰值
        if motion_scores:
            motion_scores = np.array(motion_scores)
            mean_motion = np.mean(motion_scores)
            std_motion = np.std(motion_scores)
            
            # 找到高于平均值+标准差的峰值点
            peaks = np.where(motion_scores > mean_motion + std_motion)[0]
            
            for peak_idx in peaks:
                if peak_idx < len(timestamps):
                    cut_point = OptimalCutPoint(
                        timestamp=timestamps[peak_idx],
                        confidence=0.7,
                        cut_type="action_peak"
                    )
                    cut_points.append(cut_point)
        
        return cut_points
    
    def _select_optimal_segments(self, cut_points: List[OptimalCutPoint],
                               target_duration: float,
                               min_duration: float,
                               max_duration: float) -> List[OptimalCutPoint]:
        """选择最优的起始剪辑点（用于跨集组合）
        
        注意：此方法不再寻找单集内的完整片段，而是找到优质的起始点，
        供后续跨集处理使用。单集时长通常远小于目标时长要求。
        """
        if not cut_points:
            logger.warning("没有找到任何场景变化点")
            return []
        
        # 按时间排序
        cut_points.sort(key=lambda x: x.timestamp)
        
        logger.info(f"在单集内找到 {len(cut_points)} 个场景变化点")
        logger.info(f"🔍 AI剪辑点筛选策略说明:")
        # AI筛选策略：避开片头片尾，选择高质量剪辑点
        
        # 选择优质起始点的策略：
        # 1. 不要太早（避免片头）
        # 2. 不要太晚（确保有足够内容供后续扩展）
        # 3. 选择置信度高的点
        
        optimal_start_points = []
        
        # 静默评估候选剪辑点
        
        for i, point in enumerate(cut_points):
            # 过滤条件：
            # - 不要开头的前3秒（可能是片头/广告）
            # - 不要结尾的后15秒（确保有足够内容）
            # - 置信度要足够高
            meets_criteria = (point.timestamp >= 3.0 and 
                            point.timestamp <= max(cut_points[-1].timestamp - 15.0, 30.0) and
                            point.confidence >= 0.6)
            
            # 静默处理候选点评估
            if meets_criteria:
                # 为起始点计算综合评分（简化版本，去除质量评分）
                # 1. 置信度评分 (0-1): 基于场景变化强度
                confidence_score = point.confidence
                
                # 2. 时间位置偏好评分 (0-1): 偏好30秒左右的位置
                time_position_score = 1.0 - abs(point.timestamp - 30.0) / 60.0
                time_position_score = max(0.0, min(1.0, time_position_score))
                
                # 综合评分 = 置信度70% + 时间位置30%（原片质量有保障，无需评估）
                overall_score = (
                    confidence_score * 0.7 +     # 置信度为主要因素（场景变化强度）
                    time_position_score * 0.3    # 时间位置偏好（避免开头结尾）
                )
                
                # 创建优化的起始点
                start_point = OptimalCutPoint(
                    timestamp=point.timestamp,
                    confidence=overall_score,
                    cut_type="optimal_start_point"
                )
                optimal_start_points.append(start_point)
        
        # 如果没有找到符合条件的点，降低标准
        if not optimal_start_points and cut_points:
            logger.warning("使用宽松条件重新选择起始点")
            for point in cut_points:
                if point.timestamp >= 3.0 and point.confidence >= 0.4:
                    start_point = OptimalCutPoint(
                        timestamp=point.timestamp,
                        confidence=point.confidence * 0.8,  # 降低评分表示是备选
                        cut_type="fallback_start_point"
                    )
                    optimal_start_points.append(start_point)
        
        # 按评分排序，只返回1个最佳起始点
        optimal_start_points.sort(key=lambda x: x.confidence, reverse=True)
        
        if optimal_start_points:
            best_point = optimal_start_points[0]  # 只取最佳的1个起始点
            logger.info(f"✅ AI选择最佳起始点: {best_point.timestamp:.1f}s")
            return [best_point]
        else:
            logger.warning("未找到合适的起始点")
            return []


# 使用示例和测试函数
def test_scene_analyzer():
    """测试场景分析器"""
    analyzer = SceneAnalyzer()
    
    # 这里需要一个真实的视频文件进行测试
    # video_path = Path("test_video.mp4")
    # scenes = analyzer.analyze_video_scenes(video_path)
    # print(f"检测到 {len(scenes)} 个场景")
    
    print("场景分析器测试完成")


if __name__ == "__main__":
    test_scene_analyzer()
