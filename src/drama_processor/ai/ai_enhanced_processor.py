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
        """使用AI生成起始点"""
        if not project.episodes:
            return []
        
        try:
            # 使用AI分析找到最佳剪辑点
            optimal_points = self._find_optimal_segments_with_ai(project)
            
            if not optimal_points:
                logger.warning("AI未找到合适的剪辑点，回退到随机方式")
                return self._generate_random_start_points_with_dedup(project, count)
            
            # 应用去重逻辑过滤已使用的剪辑点
            if self.enable_deduplication:
                filtered_points = []
                for point in optimal_points:
                    # 假设AI剪辑点都在第一集（episode_idx = 0）
                    if not self._is_cut_point_excluded(0, point.timestamp):
                        filtered_points.append(point)
                    else:
                        logger.debug(f"跳过已使用的AI剪辑点: {point.timestamp:.1f}s")
                
                if not filtered_points:
                    logger.warning("所有AI剪辑点都已被使用，回退到随机方式")
                    return self._generate_random_start_points_with_dedup(project, count)
                
                optimal_points = filtered_points
            
            # 选择最佳的剪辑点
            selected_points = optimal_points[:count]
            start_points = []
            
            for point in selected_points:
                episode_idx = 0  # 假设AI剪辑点都在第一集
                start_points.append((episode_idx, point.timestamp))
                
                # 记录已使用的剪辑点
                if self.enable_deduplication:
                    self._add_used_cut_point(episode_idx, point.timestamp)
                
                logger.info(f"✅ AI选择剪辑点: 第{episode_idx+1}集, {point.timestamp:.1f}s")
            
            # 如果AI剪辑点不够，用随机方式补充
            if len(start_points) < count:
                remaining_count = count - len(start_points)
                logger.info(f"AI剪辑点不足，用随机方式补充 {remaining_count} 个")
                additional_points = self._generate_random_start_points_with_dedup(project, remaining_count)
                start_points.extend(additional_points)
            
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
        """重写父类方法，添加AI智能场景检测功能"""
        logger.info(f"🤖 AI增强处理 | 剧：{project.name} | 第 {material_idx} / {material_total} 条")
        logger.info(f"🎯 分配起始点: 第{start_ep_idx}集，偏移{start_offset:.1f}秒")
        
        try:
            # AI场景分析和智能剪辑点选择（针对分配的集数范围）
            if self.enable_scene_detection and self.scene_analyzer:
                logger.info(f"🔍 正在对第{start_ep_idx}集及后续集数执行AI场景分析...")
                optimal_segments = self._find_optimal_segments_with_ai_for_material(
                    project, start_ep_idx, start_offset, material_idx, material_total
                )
                if optimal_segments:
                    logger.info(f"✅ AI找到 {len(optimal_segments)} 个最佳剪辑点")
                    # 使用AI推荐的剪辑点进行智能处理
                    processing_time = self._process_with_ai_segments(
                        project, optimal_segments, material_idx, 
                        output_path, temp_root, run_suffix, material_total, min_sec, max_sec
                    )
                    return processing_time
                else:
                    logger.info("ℹ️ 未找到合适的AI剪辑点，将使用传统方式")
            
            # 执行常规处理流程
            logger.info("📋 开始执行视频处理...")
            processing_time = super().process_single_material(
                project, material_idx, start_ep_idx, start_offset, 
                output_path, temp_root, run_suffix, material_total
            )
            
            # 保存AI处理元数据
            if self.enable_scene_detection:
                self._save_ai_metadata(Path(output_path), {
                    'scene_detection_enabled': self.enable_scene_detection,
                    'processing_timestamp': time.time()
                })
            
            logger.info(f"✅ AI智能场景处理完成，耗时: {processing_time:.2f}秒")
            return processing_time
            
        except Exception as e:
            logger.error(f"❌ AI智能场景处理失败: {e}")
            # 降级到常规处理
            logger.info("🔄 降级到常规处理模式")
            return super().process_single_material(
                project, material_idx, start_ep_idx, start_offset, 
                output_path, temp_root, run_suffix, material_total
            )
    
    def _find_optimal_segments_with_ai(self, project: DramaProject) -> List[OptimalCutPoint]:
        """使用AI寻找最佳剪辑片段"""
        if not self.enable_scene_detection or not self.scene_analyzer or not project.episodes:
            return []
        
        try:
            # 选择主要集数进行分析（通常是第一集）
            main_episode = project.episodes[0]
            logger.info(f"📹 分析视频文件: {main_episode.file_path}")
            
            # 使用AI分析器寻找最佳剪辑点
            optimal_points = self.scene_analyzer.find_optimal_cut_points(
                video_path=main_episode.file_path,
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
                logger.info(f"⚠️ 使用{quality_threshold}阈值未找到剪辑点，降低阈值重试...")
                quality_threshold = 0.1
                high_quality_points = [
                    point for point in optimal_points 
                    if point.confidence > quality_threshold
                ]
            
            logger.info(f"🎯 AI场景分析完成: {len(optimal_points)} -> {len(high_quality_points)} 个高质量剪辑点 (阈值: {quality_threshold})")
            return high_quality_points
            
        except Exception as e:
            logger.error(f"⚠️ AI场景分析失败: {e}")
            return []
    
    def _find_optimal_segments_with_ai_for_material(self, project: DramaProject, 
                                                  start_ep_idx: int, start_offset: float,
                                                  material_idx: int, material_total: int) -> List[OptimalCutPoint]:
        """针对特定素材找到1个AI剪辑起始点，优先从较早集数开始查找"""
        try:
            if not project.episodes:
                logger.warning(f"项目没有集数信息")
                return []
            
            # 计算素材应该覆盖的集数范围
            episodes_per_material = max(1, len(project.episodes) // material_total)
            
            # 智能起始点：优先从较早的集数开始，确保有足够内容
            # 如果分配的起始集数太靠后，往前调整
            total_episodes = len(project.episodes)
            
            # 计算理想的查找起始点：确保后续有足够集数生成长时间素材
            min_episodes_needed = max(5, episodes_per_material * 2)  # 至少需要5集或2倍素材长度
            
            # 避免最后10集作为起始点的限制
            last_10_episodes_threshold = max(0, total_episodes - 10)
            
            # 如果原始起始点在最后10集中，随机选择一个更早的位置
            adjusted_start_idx = start_ep_idx
            if start_ep_idx >= last_10_episodes_threshold:
                # 随机选择一个不在最后10集的起始点
                max_valid_start = last_10_episodes_threshold - 1
                if max_valid_start >= 0:
                    adjusted_start_idx = random.randint(0, max_valid_start)
                    logger.info(f"🚫 避免最后10集：从第{start_ep_idx+1}集随机调整到第{adjusted_start_idx+1}集")
                else:
                    adjusted_start_idx = 0
                    logger.info(f"🚫 避免最后10集：剧集太少，调整到第1集")
            
            # 如果调整后的起始点仍然没有足够内容，进一步往前调整
            if adjusted_start_idx + min_episodes_needed > total_episodes:
                adjusted_start_idx = max(0, total_episodes - min_episodes_needed)
                # 但仍要确保不在最后10集中
                if adjusted_start_idx >= last_10_episodes_threshold:
                    # 随机选择一个不在最后10集的起始点
                    max_valid_start = last_10_episodes_threshold - 1
                    if max_valid_start >= 0:
                        adjusted_start_idx = random.randint(0, max_valid_start)
                        logger.info(f"🔄 进一步随机调整起始点：调整到第{adjusted_start_idx+1}集，确保有足够内容且避开最后10集")
                    else:
                        adjusted_start_idx = 0
                        logger.info(f"🔄 进一步调整起始点：剧集太少，调整到第1集")
            
            # 查找范围：从调整后的起始点开始，覆盖足够的集数
            search_start_idx = adjusted_start_idx
            search_end_idx = min(search_start_idx + min_episodes_needed, total_episodes)
            
            # 获取剧集名称列表用于日志显示
            episode_names = []
            for ep_idx in range(search_start_idx, min(search_start_idx + 3, search_end_idx)):  # 只显示前3集
                episode_names.append(f"第{ep_idx+1}集")
            if search_end_idx - search_start_idx > 3:
                episode_names.append(f"...第{search_end_idx}集")
            episode_range_str = ", ".join(episode_names)
            
            logger.info(f"📺 素材{material_idx}AI查找范围: {episode_range_str} (共{search_end_idx-search_start_idx}集)")
            
            all_cut_points = []
            
            # 只分析选集范围内的第一集来查找最佳剪辑点
            max_episodes_to_analyze = 1  # 只分析第一集
            
            for i in range(max_episodes_to_analyze):
                episode_idx = search_start_idx + i
                episode = project.episodes[episode_idx]
                logger.info(f"🔍 分析第{episode_idx+1}集: {episode.file_path.name}")
                
                try:
                    # 对该集找到剪辑点
                    episode_points = self.scene_analyzer.find_optimal_cut_points(
                        video_path=episode.file_path,
                        target_duration=600,  # 默认10分钟
                        min_duration=300,     # 最小5分钟
                        max_duration=900      # 最大15分钟
                    )
                    
                    # 为剪辑点添加集数信息
                    for point in episode_points:
                        # 创建新的剪辑点，保持原始时间戳便于处理
                        episode_point = OptimalCutPoint(
                            timestamp=point.timestamp,  # 保持集内时间戳
                            confidence=point.confidence,
                            cut_type=point.cut_type
                        )
                        # 添加集数信息（通过属性扩展）
                        episode_point.episode_idx = episode_idx
                        episode_point.episode_path = episode.file_path
                        
                        all_cut_points.append(episode_point)
                
                    logger.info(f"📊 第{episode_idx+1}集找到 {len(episode_points)} 个剪辑点")
                    
                except Exception as e:
                    logger.warning(f"⚠️ 分析第{episode_idx+1}集失败: {e}")
            
            logger.info(f"🎯 总共找到 {len(all_cut_points)} 个AI剪辑点")
            
            # 过滤低质量的剪辑点
            quality_threshold = 0.3
            high_quality_points = [
                point for point in all_cut_points 
                if point.confidence > quality_threshold
            ]
            
            # 如果还是没有找到，进一步降低阈值
            if not high_quality_points and all_cut_points:
                logger.info(f"⚠️ 使用{quality_threshold}阈值未找到剪辑点，降低阈值重试...")
                quality_threshold = 0.1
                high_quality_points = [
                    point for point in all_cut_points 
                    if point.confidence > quality_threshold
                ]
            
            # 实现多样性剪辑点选择策略：避免重复内容
            if high_quality_points:
                # 按置信度排序，从高到低
                sorted_points = sorted(high_quality_points, key=lambda p: p.confidence, reverse=True)
                
                # 寻找未被使用且不在排除区域的剪辑点
                selected_point = None
                for point in sorted_points:
                    if not self._is_cut_point_excluded(point.episode_idx, point.timestamp):
                        selected_point = point
                        break
                
                if selected_point:
                    # 记录已使用的剪辑点
                    self._add_used_cut_point(selected_point.episode_idx, selected_point.timestamp)
                    logger.info(f"🎯 素材{material_idx}AI分析完成: 选择多样化起始点 (第{selected_point.episode_idx+1}集 {selected_point.timestamp:.1f}s)")
                    return [selected_point]
                else:
                    # 所有高质量点都在排除区域，使用质量最高的点但增加警告
                    best_point = sorted_points[0]
                    self._add_used_cut_point(best_point.episode_idx, best_point.timestamp)
                    logger.warning(f"⚠️ 素材{material_idx}所有剪辑点都在排除区域，使用最佳点 (第{best_point.episode_idx+1}集 {best_point.timestamp:.1f}s)")
                    return [best_point]
            else:
                logger.warning(f"⚠️ 素材{material_idx}未找到合适的AI起始点")
                return []
            
        except Exception as e:
            logger.error(f"⚠️ 素材{material_idx}AI场景分析失败: {e}")
            return []
    
    
    def _process_with_ai_segments(self, project: DramaProject, 
                                optimal_segments: List[OptimalCutPoint],
                                material_idx: int, output_path: str, 
                                temp_root: str, run_suffix: Optional[str], 
                                material_total: int, min_sec: float, max_sec: float) -> float:
        """根据AI推荐的剪辑起始点处理视频片段，剪到符合时长的集数结尾"""
        import time
        from pathlib import Path
        from ..utils.video import probe_duration
        
        logger.info(f"🎬 开始基于AI起始点的智能处理...")
        start_time = time.time()
        
        # 只处理第一个（也是唯一的）AI剪辑点作为起始
        if not optimal_segments:
            logger.warning("⚠️ 没有AI剪辑点可用")
            return 0.0
        
        ai_start_point = optimal_segments[0]  # 只使用第一个剪辑点
        
        try:
            # 确认起始点信息
            if not (hasattr(ai_start_point, 'episode_idx') and hasattr(ai_start_point, 'episode_path')):
                logger.error("❌ AI剪辑点缺少集数信息")
                return 0.0
            
            start_episode_idx = ai_start_point.episode_idx
            start_timestamp = ai_start_point.timestamp
            
            logger.info(f"🎯 AI起始点: 第{start_episode_idx+1}集 {start_timestamp:.1f}s")
            
            # 使用传入的时长范围参数
            min_duration = min_sec  # 8分钟
            max_duration = max_sec  # 15分钟
            
            logger.info(f"📏 目标时长范围: {min_duration}s-{max_duration}s ({min_duration/60:.1f}-{max_duration/60:.1f}分钟)")
            
            # 计算从AI起始点到符合时长范围的集数结尾
            segments_info = self._calculate_segments_to_episode_end(
                project, start_episode_idx, start_timestamp, min_duration, max_duration
            )
            
            if not segments_info:
                logger.warning("⚠️ 无法找到符合时长范围的片段组合")
                return 0.0
            
            total_duration = segments_info['total_duration']
            final_episode_idx = segments_info['end_episode_idx']
            segment_list = segments_info['segments']
            
            logger.info(f"✂️ 最终剪辑方案: 从第{start_episode_idx+1}集{start_timestamp:.1f}s 到第{final_episode_idx+1}集结尾")
            logger.info(f"📊 总时长: {total_duration:.1f}s ({total_duration/60:.1f}分钟)")
            logger.info(f"📝 包含{len(segment_list)}个片段")
            
            # 使用父类的传统处理方法来处理这些片段
            processing_time = self._process_multi_episode_segments(
                segment_list, output_path, temp_root, material_idx, material_total
            )
            
            logger.info(f"✅ AI智能处理完成！总时长: {total_duration:.1f}s，耗时: {processing_time:.2f}秒")
            return processing_time
            
        except Exception as e:
            logger.error(f"❌ 处理AI片段失败: {e}")
            return 0.0
    
    def _calculate_segments_to_episode_end(self, project: DramaProject, 
                                         start_episode_idx: int, start_timestamp: float,
                                         min_duration: float, max_duration: float) -> dict:
        """计算从AI起始点到集数结尾的片段组合"""
        from ..utils.video import probe_duration
        
        segments = []
        total_duration = 0.0
        current_ep_idx = start_episode_idx
        
        # 第一个片段：从AI起始点到第一集结尾
        if current_ep_idx < len(project.episodes):
            first_episode = project.episodes[current_ep_idx]
            try:
                episode_duration = probe_duration(first_episode.file_path)
                first_segment_duration = episode_duration - start_timestamp
                
                if first_segment_duration > 0:
                    segments.append({
                        'episode_idx': current_ep_idx,
                        'episode_path': first_episode.file_path,
                        'start_time': start_timestamp,
                        'end_time': episode_duration,
                        'duration': first_segment_duration
                    })
                    total_duration += first_segment_duration
                    logger.info(f"📋 片段1: 第{current_ep_idx}集 {start_timestamp:.1f}s-{episode_duration:.1f}s ({first_segment_duration:.1f}s)")
                
            except Exception as e:
                logger.warning(f"⚠️ 无法获取第{current_ep_idx}集时长: {e}")
                return None
        
        # 添加后续完整集数，直到达到时长要求
        current_ep_idx += 1
        while current_ep_idx < len(project.episodes):
            episode = project.episodes[current_ep_idx]
            try:
                episode_duration = probe_duration(episode.file_path)
                
                # 检查加上这一集是否会超出最大时长
                if total_duration + episode_duration > max_duration:
                    # 如果当前总时长已经达到最小要求，就停止
                    if total_duration >= min_duration:
                        logger.info(f"📏 已达到时长要求，停止在第{current_ep_idx-1}集结尾")
                        break
                    # 如果还没达到最小要求，但加上下一集会超出最大值，需要部分添加
                    else:
                        remaining_duration = max_duration - total_duration
                        if remaining_duration > 30:  # 至少要有30秒
                            segments.append({
                                'episode_idx': current_ep_idx,
                                'episode_path': episode.file_path,
                                'start_time': 0.0,
                                'end_time': remaining_duration,
                                'duration': remaining_duration
                            })
                            total_duration += remaining_duration
                            logger.info(f"📋 片段{len(segments)}: 第{current_ep_idx}集 0.0s-{remaining_duration:.1f}s ({remaining_duration:.1f}s) [部分]")
                        break
                else:
                    # 添加完整集数
                    segments.append({
                        'episode_idx': current_ep_idx,
                        'episode_path': episode.file_path,
                        'start_time': 0.0,
                        'end_time': episode_duration,
                        'duration': episode_duration
                    })
                    total_duration += episode_duration
                    logger.info(f"📋 片段{len(segments)}: 第{current_ep_idx}集 0.0s-{episode_duration:.1f}s ({episode_duration:.1f}s) [完整]")
                
                # 检查是否已经达到理想时长
                if total_duration >= min_duration:
                    # 如果已经超过最小时长，且当前是完整集的结尾，可以考虑停止
                    if segments[-1]['end_time'] == episode_duration:  # 当前片段是完整集
                        if total_duration <= max_duration:
                            logger.info(f"✅ 达到理想时长，在第{current_ep_idx}集结尾结束")
                            break
                
                current_ep_idx += 1
                
            except Exception as e:
                logger.warning(f"⚠️ 无法获取第{current_ep_idx}集时长: {e}")
                break
        
        # 检查最终时长是否符合要求
        if total_duration < min_duration:
            # 兜底处理：如果已经剪到最后一集还不够，直接接受
            final_episode_idx = segments[-1]['episode_idx'] if segments else start_episode_idx
            if final_episode_idx >= len(project.episodes) - 1:  # 已经是最后一集
                logger.info(f"🎬 已剪到最后一集，虽然时长{total_duration:.1f}s 小于最小要求{min_duration:.1f}s，但直接接受")
            else:
                logger.warning(f"⚠️ 总时长{total_duration:.1f}s 小于最小要求{min_duration:.1f}s")
                return None
        
        if total_duration > max_duration:
            logger.warning(f"⚠️ 总时长{total_duration:.1f}s 超过最大限制{max_duration:.1f}s")
            # 尝试裁剪最后一个片段
            if len(segments) > 0:
                excess = total_duration - max_duration
                last_segment = segments[-1]
                if last_segment['duration'] > excess + 30:  # 至少保留30秒
                    last_segment['end_time'] -= excess
                    last_segment['duration'] -= excess
                    total_duration = max_duration
                    logger.info(f"🔧 裁剪最后片段，调整后总时长: {total_duration:.1f}s")
                else:
                    return None
        
        final_episode_idx = segments[-1]['episode_idx'] if segments else start_episode_idx
        
        return {
            'segments': segments,
            'total_duration': total_duration,
            'start_episode_idx': start_episode_idx,
            'end_episode_idx': final_episode_idx
        }
    
    def _process_multi_episode_segments(self, segment_list: list, output_path: str, 
                                      temp_root: str, material_idx: int, material_total: int) -> float:
        """处理多集片段，调用父类方法"""
        import time
        from pathlib import Path
        from ..core.encoder import VideoEncoder
        
        start_time_processing = time.time()
        
        try:
            # 创建临时工作目录
            temp_dir = Path(temp_root) / f"ai_material_{material_idx}"
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            # 转换为父类期望的格式 (episode_path, start_time, end_time)
            segments_for_encoder = []
            for seg in segment_list:
                segments_for_encoder.append((
                    str(seg['episode_path']),
                    seg['start_time'],
                    seg['end_time']
                ))
            
            # 使用父类的encoder来处理 (重用父类的水印配置)
            encoder = self.encoder
            
            # 调用encoder的处理方法 (类似于build_segments_at_episode_boundaries的输出处理)
            logger.info(f"🎬 开始处理 {len(segments_for_encoder)} 个片段...")
            
            # 这里简化处理，直接使用ffmpeg拼接
            self._process_segments_with_ffmpeg(
                segments_for_encoder, output_path, str(temp_dir), material_idx
            )
            
            processing_time = time.time() - start_time_processing
            return processing_time
            
        except Exception as e:
            logger.error(f"❌ 多集片段处理失败: {e}")
            return 0.0
    
    def _process_segments_with_ffmpeg(self, segments: list, output_path: str, 
                                    temp_dir: str, material_idx: int):
        """使用ffmpeg处理和拼接片段"""
        import subprocess
        from pathlib import Path
        
        temp_parts = []
        
        # 处理每个片段
        for i, (episode_path, start_time, end_time) in enumerate(segments, 1):
            duration = end_time - start_time
            temp_part = Path(temp_dir) / f"part_{i:03d}.mp4"
            
            cmd = [
                'ffmpeg', '-y',
                '-i', episode_path,
                '-ss', str(start_time),
                '-t', str(duration),
                '-c', 'copy',
                '-avoid_negative_ts', 'make_zero',
                str(temp_part)
            ]
            
            logger.info(f"🎞️ 处理片段 {i}/{len(segments)}: {Path(episode_path).name} ({start_time:.1f}s-{end_time:.1f}s)")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                raise RuntimeError(f"片段{i}处理失败: {result.stderr}")
            
            temp_parts.append(str(temp_part))
        
        # 如果只有一个片段，直接复制
        if len(temp_parts) == 1:
            import shutil
            shutil.move(temp_parts[0], output_path)
            logger.info(f"✅ 单片段输出: {output_path}")
        else:
            # 创建拼接列表文件
            concat_list = Path(temp_dir) / "concat_list.txt"
            with open(concat_list, 'w', encoding='utf-8') as f:
                for part in temp_parts:
                    f.write(f"file '{part}'\n")
            
            # 拼接片段
            cmd = [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', str(concat_list),
                '-c', 'copy',
                output_path
            ]
            
            logger.info(f"🔗 拼接 {len(temp_parts)} 个片段...")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if result.returncode != 0:
                raise RuntimeError(f"拼接失败: {result.stderr}")
            
            logger.info(f"✅ 拼接完成: {output_path}")
    
    def _process_ai_segment(self, video_path: Path, start_time: float, 
                          end_time: float, output_path: str, temp_dir: str):
        """处理单个AI推荐的视频片段"""
        import subprocess
        
        duration = end_time - start_time
        
        # 使用ffmpeg剪辑片段
        cmd = [
            'ffmpeg',
            '-y',  # 覆盖输出文件
            '-i', str(video_path),
            '-ss', str(start_time),
            '-t', str(duration),
            '-c', 'copy',  # 复制编码，快速处理
            '-avoid_negative_ts', 'make_zero',
            output_path
        ]
        
        logger.debug(f"执行命令: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=300  # 5分钟超时
            )
            
            if result.returncode != 0:
                logger.error(f"ffmpeg错误: {result.stderr}")
                raise RuntimeError(f"视频剪辑失败: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            logger.error("ffmpeg处理超时")
            raise RuntimeError("视频处理超时")
        except Exception as e:
            logger.error(f"视频处理异常: {e}")
            raise
    
    
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
