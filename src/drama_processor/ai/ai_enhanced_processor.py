"""AI增强的短剧处理器"""

import logging
import random
import json
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
import time
import hashlib

from ..core.processor import DramaProcessor
from ..models.config import ProcessingConfig
from ..models.project import DramaProject
from ..models.episode import Episode

from .scene_detection.scene_analyzer import SceneAnalyzer, OptimalCutPoint

logger = logging.getLogger(__name__)


class AIEnhancedProcessor(DramaProcessor):
    """AI增强的短剧处理器"""
    
    def __init__(self, config: ProcessingConfig,
                 enable_ai_scene_detection: bool = True,
                 status_callback=None):
        """初始化AI增强处理器
        
        Args:
            config: 处理配置
            enable_ai_scene_detection: 是否启用AI场景检测
            status_callback: 状态回调函数
        """
        super().__init__(config, status_callback)
        
        self.enable_scene_detection = enable_ai_scene_detection
        
        # 去重功能配置
        self.enable_deduplication = config.enable_deduplication
        
        # 用于避免重复的全局剪辑点记录（仅在启用去重时使用）
        self.used_cut_points = []  # List[Tuple[int, float]] - (episode_idx, timestamp)
        self.exclusion_radius = 30.0  # 排除半径：30秒
        
        # 持久化存储配置（仅在启用去重时初始化）
        if self.enable_deduplication:
            self.cut_points_storage_dir = Path(config.temp_dir or "/tmp") / "cut_points_history"
            self.cut_points_storage_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.cut_points_storage_dir = None
        
        # 初始化AI组件
        if self.enable_scene_detection:
            logger.info("正在初始化AI智能场景检测组件...")
            self.scene_analyzer = SceneAnalyzer()
            logger.info("AI智能场景检测已启用")
        else:
            self.scene_analyzer = None
            logger.info("AI场景检测已禁用，将使用传统处理方式")
    
    def _get_drama_hash(self, drama_name: str) -> str:
        """生成剧集的唯一标识符"""
        return hashlib.md5(drama_name.encode('utf-8')).hexdigest()[:8]
    
    def _get_cut_points_file(self, drama_name: str) -> Path:
        """获取剪辑点存储文件路径"""
        if not self.enable_deduplication or not self.cut_points_storage_dir:
            raise ValueError("去重功能未启用")
        
        drama_hash = self._get_drama_hash(drama_name)
        return self.cut_points_storage_dir / f"{drama_hash}_{drama_name}.json"
    
    def _load_used_cut_points(self, drama_name: str) -> List[Tuple[int, float]]:
        """从文件加载已使用的剪辑点"""
        if not self.enable_deduplication:
            return []
        
        try:
            cut_points_file = self._get_cut_points_file(drama_name)
            if not cut_points_file.exists():
                return []
            
            with open(cut_points_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 转换为元组列表
            used_points = [(item['episode_idx'], item['timestamp']) for item in data.get('used_cut_points', [])]
            logger.info(f"从文件加载了 {len(used_points)} 个已使用的剪辑点：{drama_name}")
            return used_points
            
        except Exception as e:
            logger.warning(f"加载剪辑点文件失败：{e}")
            return []
    
    def _save_used_cut_points(self, drama_name: str, cut_points: List[Tuple[int, float]]):
        """保存已使用的剪辑点到文件"""
        if not self.enable_deduplication:
            return
        
        try:
            cut_points_file = self._get_cut_points_file(drama_name)
            
            # 准备数据结构
            from datetime import datetime
            data = {
                'drama_name': drama_name,
                'last_updated': datetime.now().isoformat(),
                'used_cut_points': [
                    {'episode_idx': ep_idx, 'timestamp': ts} 
                    for ep_idx, ts in cut_points
                ]
            }
            
            # 确保目录存在
            cut_points_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 写入文件
            with open(cut_points_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"已保存 {len(cut_points)} 个剪辑点到文件：{drama_name}")
            
        except Exception as e:
            logger.error(f"保存剪辑点文件失败：{e}")
    
    def _add_used_cut_point(self, episode_idx: int, timestamp: float):
        """添加一个已使用的剪辑点"""
        if not self.enable_deduplication:
            return
        
        self.used_cut_points.append((episode_idx, timestamp))
        logger.debug(f"添加已使用剪辑点: Episode {episode_idx}, {timestamp:.1f}s")

    def _is_cut_point_excluded(self, episode_idx: int, timestamp: float) -> bool:
        """检查剪辑点是否在排除区域内"""
        for used_ep_idx, used_timestamp in self.used_cut_points:
            if used_ep_idx == episode_idx:
                # 同一集内检查时间距离
                if abs(timestamp - used_timestamp) < self.exclusion_radius:
                    return True
        return False
    
    def process_project_materials(self, project: DramaProject, out_dir: str, 
                                run_suffix: Optional[str], start_index: int, 
                                total_to_make: int, temp_root: str, drama_date: Optional[str] = None) -> Tuple[int, float]:
        """处理项目素材，支持去重功能
        
        在处理前加载历史剪辑点，处理后保存新的剪辑点
        """
        # 在启用去重时，加载历史剪辑点
        if self.enable_deduplication:
            logger.info(f"🔄 启用去重模式，加载历史剪辑点：{project.name}")
            historical_points = self._load_used_cut_points(project.name)
            self.used_cut_points.extend(historical_points)
            
            if historical_points:
                logger.info(f"✅ 已加载 {len(historical_points)} 个历史剪辑点")
            else:
                logger.info("📝 未发现历史剪辑点，开始新记录")
        
        # 记录处理前的剪辑点数量
        initial_points_count = len(self.used_cut_points)
        
        # 调用父类的处理方法
        completed_count, total_time = super().process_project_materials(
            project, out_dir, run_suffix, start_index, total_to_make, temp_root, drama_date
        )
        
        # 在启用去重时，保存新增的剪辑点
        if self.enable_deduplication and completed_count > 0:
            new_points_count = len(self.used_cut_points) - initial_points_count
            if new_points_count > 0:
                logger.info(f"💾 保存新增的 {new_points_count} 个剪辑点")
                self._save_used_cut_points(project.name, self.used_cut_points)
            else:
                logger.info("🔍 未生成新的剪辑点")
        
        return completed_count, total_time
    
    def generate_start_points(self, project: DramaProject, count: int) -> List[Tuple[int, float]]:
        """生成起始点，支持去重和AI场景检测"""
        if count <= 0:
            return []
        
        logger.info(f"🎯 开始生成 {count} 个起始点")
        
        # 如果启用AI场景检测，使用AI方法
        if self.enable_scene_detection and self.scene_analyzer:
            return self._generate_ai_start_points(project, count)
        
        # 否则使用父类的随机方法，但加上去重逻辑
        return self._generate_random_start_points_with_dedup(project, count)
    
    def _generate_ai_start_points(self, project: DramaProject, count: int) -> List[Tuple[int, float]]:
        """使用AI生成起始点 - 从随机选择的集数开始分析"""
        if not project.episodes:
            return []
        
        start_points = []
        num_episodes = len(project.episodes)
        
        try:
            # 为每个素材独立选择随机起始集和AI剪辑点
            for material_idx in range(count):
                # 随机选择起始集数
                random_ep_idx = random.randrange(num_episodes)
                
                # 使用AI分析该集数找到最佳剪辑点
                optimal_points = self._find_optimal_segments_with_ai_for_episode(project, random_ep_idx)
                
                if optimal_points:
                    # 应用去重逻辑过滤已使用的剪辑点
                    if self.enable_deduplication:
                        filtered_points = []
                        for point in optimal_points:
                            if not self._is_cut_point_excluded(random_ep_idx, point.timestamp):
                                filtered_points.append(point)
                            else:
                                logger.debug(f"跳过已使用的AI剪辑点: 第{random_ep_idx+1}集 {point.timestamp:.1f}s")
                        
                        if filtered_points:
                            optimal_points = filtered_points
                        else:
                            # 如果该集的AI剪辑点都被使用了，回退到该集的随机点
                            logger.debug(f"第{random_ep_idx+1}集的AI剪辑点都已使用，使用随机点")
                            optimal_points = None
                
                if optimal_points:
                    # 选择置信度最高的剪辑点
                    best_point = max(optimal_points, key=lambda p: p.confidence)
                    start_points.append((random_ep_idx, best_point.timestamp))
                    
                    # 记录已使用的剪辑点
                    if self.enable_deduplication:
                        self._add_used_cut_point(random_ep_idx, best_point.timestamp)
                    
                    logger.info(f"✅ AI选择剪辑点: 第{random_ep_idx+1}集, {best_point.timestamp:.1f}s (置信度: {best_point.confidence:.2f})")
                else:
                    # AI分析失败，回退到该集的随机点
                    episode = project.episodes[random_ep_idx]
                    if episode.duration:
                        max_offset = min(60.0, episode.duration / 3.0)
                        random_offset = round(random.uniform(0, max_offset), 3)
                    else:
                        random_offset = 0.0
                    
                    start_points.append((random_ep_idx, random_offset))
                    logger.info(f"⚠️ AI分析失败，使用随机点: 第{random_ep_idx+1}集, {random_offset:.1f}s")
            
            return start_points
            
        except Exception as e:
            logger.error(f"AI生成起始点失败: {e}")
            return self._generate_random_start_points_with_dedup(project, count)
    
    def _generate_random_start_points_with_dedup(self, project: DramaProject, count: int) -> List[Tuple[int, float]]:
        """生成随机起始点，支持去重"""
        if not self.enable_deduplication:
            # 如果未启用去重，直接调用父类方法
            start_points = super().generate_start_points(project, count)
            # 记录生成的起始点（不去重，但记录用于后续参考）
            for ep_idx, timestamp in start_points:
                self._add_used_cut_point(ep_idx, timestamp)
            return start_points
        
        # 启用去重的随机生成逻辑
        start_points = []
        max_attempts = count * 10  # 最大尝试次数，避免死循环
        attempts = 0
        
        while len(start_points) < count and attempts < max_attempts:
            attempts += 1
            
            # 生成一个随机起始点
            temp_points = super().generate_start_points(project, 1)
            if not temp_points:
                break
            
            ep_idx, timestamp = temp_points[0]
            
            # 检查是否与已使用的剪辑点冲突
            if not self._is_cut_point_excluded(ep_idx, timestamp):
                start_points.append((ep_idx, timestamp))
                self._add_used_cut_point(ep_idx, timestamp)
                logger.debug(f"生成随机起始点: 第{ep_idx+1}集, {timestamp:.1f}s")
            else:
                logger.debug(f"跳过冲突的随机起始点: 第{ep_idx+1}集, {timestamp:.1f}s")
        
        if len(start_points) < count:
            logger.warning(f"去重后只生成了 {len(start_points)}/{count} 个起始点")
        
        return start_points

    def _add_used_cut_point(self, episode_idx: int, timestamp: float):
        """记录已使用的剪辑点"""
        self.used_cut_points.append((episode_idx, timestamp))
        logger.debug(f"记录已使用剪辑点: 第{episode_idx+1}集 {timestamp:.1f}s")
    
    def _reset_used_cut_points(self):
        """重置已使用剪辑点记录（用于处理新的项目）"""
        self.used_cut_points.clear()
        logger.debug("重置已使用剪辑点记录")
    
    def process_single_material(self, project: DramaProject, material_idx: int, 
                              start_ep_idx: int, start_offset: float, 
                              output_path: str, temp_root: str,
                              run_suffix: Optional[str], material_total: int, 
                              min_sec: float = 480, max_sec: float = 900) -> float:
        """重写父类方法，使用AI生成的起始点进行处理"""
        logger.info(f"🤖 AI增强处理 | 剧：{project.name} | 第 {material_idx} / {material_total} 条")
        logger.info(f"🎯 使用AI起始点: 第{start_ep_idx+1}集，偏移{start_offset:.1f}秒")
        
        try:
            # 直接使用AI在generate_start_points阶段生成的优化起始点
            # 不再进行重复的AI分析，避免双重计算
            
            # 执行常规处理流程（使用AI优化的起始点）
            logger.info("📋 开始执行视频处理（基于AI优化的起始点）...")
            processing_time = super().process_single_material(
                project, material_idx, start_ep_idx, start_offset, 
                output_path, temp_root, run_suffix, material_total
            )
            
            # 保存AI处理元数据
            if self.enable_scene_detection:
                self._save_ai_metadata(Path(output_path), {
                    'scene_detection_enabled': self.enable_scene_detection,
                    'ai_optimized_start_point': True,
                    'start_episode': start_ep_idx + 1,
                    'start_offset': start_offset,
                    'processing_timestamp': time.time()
                })
            
            logger.info(f"✅ AI增强处理完成，耗时: {processing_time:.2f}秒")
            return processing_time
            
        except Exception as e:
            logger.error(f"❌ AI增强处理失败: {e}")
            # 降级到常规处理
            logger.info("🔄 降级到常规处理模式")
            return super().process_single_material(
                project, material_idx, start_ep_idx, start_offset, 
                output_path, temp_root, run_suffix, material_total
            )
    
    def _find_optimal_segments_with_ai_for_episode(self, project: DramaProject, episode_idx: int) -> List[OptimalCutPoint]:
        """使用AI寻找指定集数的最佳剪辑片段"""
        if not self.enable_scene_detection or not self.scene_analyzer or not project.episodes:
            return []
        
        if episode_idx >= len(project.episodes):
            logger.warning(f"集数索引 {episode_idx} 超出范围 (总共 {len(project.episodes)} 集)")
            return []
        
        try:
            # 分析指定集数
            target_episode = project.episodes[episode_idx]
            logger.info(f"📹 AI分析第{episode_idx+1}集: {target_episode.file_path}")
            
            # 使用AI分析器寻找最佳剪辑点
            optimal_points = self.scene_analyzer.find_optimal_cut_points(
                video_path=target_episode.file_path,
                target_duration=600,  # 默认10分钟
                min_duration=300,     # 最小5分钟
                max_duration=900      # 最大15分钟
            )
            
            # 过滤低质量的剪辑点（降低阈值，确保能找到剪辑点）
            quality_threshold = 0.3  # 降低阈值从0.6到0.3
            high_quality_points = [
                point for point in optimal_points 
                if point.confidence > quality_threshold
            ]
            
            # 如果还是没有找到，进一步降低阈值
            if not high_quality_points and optimal_points:
                logger.info(f"⚠️ 第{episode_idx+1}集使用{quality_threshold}阈值未找到剪辑点，降低阈值重试...")
                quality_threshold = 0.1
                high_quality_points = [
                    point for point in optimal_points 
                    if point.confidence > quality_threshold
                ]
            
            logger.info(f"🎯 第{episode_idx+1}集AI场景分析完成: {len(optimal_points)} -> {len(high_quality_points)} 个高质量剪辑点 (阈值: {quality_threshold})")
            return high_quality_points
            
        except Exception as e:
            logger.error(f"⚠️ 第{episode_idx+1}集AI场景分析失败: {e}")
            return []
    
    def _find_optimal_segments_with_ai(self, project: DramaProject) -> List[OptimalCutPoint]:
        """使用AI寻找最佳剪辑片段 - 兼容性方法，默认分析第一集"""
        return self._find_optimal_segments_with_ai_for_episode(project, 0)
    
    
    
    
    def _save_ai_metadata(self, result_path: Path, metadata: dict):
        """保存AI处理元数据"""
        try:
            import json
            
            metadata_path = result_path.parent / f"{result_path.stem}_ai_metadata.json"
            
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"AI元数据已保存: {metadata_path}")
            
        except Exception as e:
            logger.warning(f"保存AI元数据失败: {e}")
    
    def analyze_project_with_ai(self, project: DramaProject) -> dict:
        """使用AI分析整个项目
        
        Args:
            project: 短剧项目
            
        Returns:
            分析结果字典
        """
        analysis_result = {
            'project_name': project.name,
            'total_episodes': len(project.episodes),
            'ai_recommendations': [],
            'optimal_segments_count': 0,
            'scene_analysis': {}
        }
        
        try:
            if self.enable_scene_detection and project.episodes:
                # 分析主要集数
                main_episode = project.episodes[0]
                scenes = self.scene_analyzer.analyze_video_scenes(main_episode.file_path)
                
                # 统计场景信息
                high_quality_scenes = [s for s in scenes if s.quality_score > 0.7]
                analysis_result['scene_analysis'] = {
                    'total_scenes': len(scenes),
                    'high_quality_scenes': len(high_quality_scenes),
                    'average_scene_duration': sum(s.end_time - s.start_time for s in scenes) / len(scenes) if scenes else 0
                }
                
                analysis_result['ai_recommendations'].append(
                    f"检测到 {len(scenes)} 个场景，其中 {len(high_quality_scenes)} 个高质量场景"
                )
                
                # 寻找最佳片段
                optimal_points = self.scene_analyzer.find_optimal_cut_points(
                    main_episode.file_path, target_duration=600
                )
                analysis_result['optimal_segments_count'] = len(optimal_points)
                
                if optimal_points:
                    analysis_result['ai_recommendations'].append(
                        f"AI推荐 {len(optimal_points)} 个最佳剪辑点，可生成高质量短视频片段"
                    )
                else:
                    analysis_result['ai_recommendations'].append("未找到明显的场景变化点，建议手动选择剪辑点")
        
        except Exception as e:
            logger.error(f"AI项目分析失败: {e}")
            analysis_result['ai_recommendations'].append(f"AI分析失败: {e}")
        
        return analysis_result


# 工厂函数
def create_ai_enhanced_processor(config: ProcessingConfig, 
                               enable_scene_detection: bool = True,
                               status_callback=None) -> AIEnhancedProcessor:
    """创建AI增强处理器的工厂函数"""
    return AIEnhancedProcessor(
        config=config,
        enable_ai_scene_detection=enable_scene_detection,
        status_callback=status_callback
    )
