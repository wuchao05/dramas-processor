"""Main drama processing orchestrator."""

import logging
import os
import random
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple, Set, Callable, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter

from ..models.config import ProcessingConfig
from ..models.project import DramaProject, MaterialOutput
from ..models.episode import Episode
from ..utils.files import (
    list_episode_files, scan_drama_dirs,
    prepare_export_dir, get_latest_export_dir, count_existing_materials,
    ensure_temp_root
)
from ..utils.video import probe_video_stream, probe_duration
from ..utils.interactive import interactive_pick_dramas
from ..utils.time import human_duration
from ..utils.history import HistoryManager
from ..integrations.feishu_notification import create_feishu_notifier, FeishuNotifier

from .analyzer import VideoAnalyzer
from .segments import SegmentBuilder
from .encoder import VideoEncoder

logger = logging.getLogger(__name__)


class DramaProcessor:
    """Main drama processing orchestrator with complete dramas_process.py compatibility."""
    
    def __init__(self, config: ProcessingConfig, status_callback: Optional[Callable[[str, str], None]] = None):
        """Initialize drama processor.
        
        Args:
            config: Processing configuration
            status_callback: Optional callback function to update drama status.
                           Called with (drama_name, new_status) parameters.
        """
        self.config = config
        self.status_callback = status_callback
        
        # Initialize components
        self.analyzer = VideoAnalyzer()
        self.segment_builder = SegmentBuilder()
        
        # Prepare watermark path
        watermark_path = None
        if config.enable_watermark and config.watermark_path:
            # Convert relative path to absolute path if needed
            if not os.path.isabs(config.watermark_path):
                watermark_path = os.path.join(os.getcwd(), config.watermark_path)
            else:
                watermark_path = config.watermark_path
            
            # Check if watermark file exists
            if not os.path.exists(watermark_path):
                logger.warning(f"水印文件不存在: {watermark_path}, 将禁用水印功能")
                watermark_path = None
        
        self.encoder = VideoEncoder(config, watermark_path=watermark_path)
        self.history_manager = HistoryManager()
        
        # Initialize Feishu notifier if enabled
        self.feishu_notifier: Optional[FeishuNotifier] = None
        if config.enable_feishu_notification:
            self.feishu_notifier = create_feishu_notifier(config)
            if self.feishu_notifier:
                logger.info("飞书通知功能已启用")
            else:
                logger.warning("飞书通知功能启用失败，将跳过通知")
        
        # Set up random seed if specified
        if config.seed is not None:
            random.seed(config.seed)
            logger.info(f"Random seed set to: {config.seed}")
    
    def scan_and_discover_dramas(self, root_dir: str) -> List[str]:
        """Scan root directory for drama directories."""
        return scan_drama_dirs(root_dir)
    
    def filter_dramas_by_config(self, all_drama_dirs: List[str]) -> List[str]:
        """Filter drama directories based on config include/exclude/interactive settings."""
        # Build exclude set
        exclude_set = set()
        if self.config.exclude:
            exclude_set = set(self.config.exclude)
        
        # Handle selection logic
        if self.config.include:
            # Explicit include list
            include_set = set(self.config.include)
            drama_dirs = [d for d in all_drama_dirs 
                         if os.path.basename(d.rstrip("/")) in include_set]
            if exclude_set:
                drama_dirs = [d for d in drama_dirs 
                             if os.path.basename(d.rstrip("/")) not in exclude_set]
            logger.info(f"Processing by include: {len(drama_dirs)} dramas")
            return drama_dirs
        
        elif self.config.full:
            # Full processing
            drama_dirs = [d for d in all_drama_dirs 
                         if os.path.basename(d.rstrip("/")) not in exclude_set]
            logger.info(f"Processing all: {len(drama_dirs)} dramas")
            return drama_dirs
        
        elif not self.config.no_interactive:
            # Interactive selection
            try:
                chosen = interactive_pick_dramas(all_drama_dirs, excludes=exclude_set)
                if chosen:
                    logger.info(f"Interactive selection: {len(chosen)} dramas")
                    return chosen
                else:
                    logger.info("No dramas selected interactively")
                    return []
            except Exception as e:
                logger.warning(f"Interactive selection failed: {e}")
                return []
        
        else:
            logger.warning("No selection method specified (include/exclude/full/interactive)")
            return []
    
    def create_drama_project(self, drama_dir: str) -> DramaProject:
        """Create drama project from directory."""
        drama_name = os.path.basename(drama_dir.rstrip("/"))
        project = DramaProject(
            name=drama_name,
            source_dir=Path(drama_dir)
        )
        
        # Load episodes
        episode_files = list_episode_files(Path(drama_dir))
        episodes = []
        for i, file_path in enumerate(episode_files, 1):
            try:
                info = probe_video_stream(str(file_path))
                episode = Episode(
                    episode_number=i,
                    file_path=file_path,
                    duration=info.get("duration", 0),
                    width=info.get("w", 0),
                    height=info.get("h", 0),
                    fps=info.get("fps", 0),
                    is_safe=True  # Assume safe for now
                )
                episodes.append(episode)
            except Exception as e:
                logger.warning(f"Failed to analyze episode {i}: {e}")
        
        project.episodes = episodes
        
        # Determine reference resolution
        if self.config.canvas:
            if self.config.canvas.lower() == "first" and episodes:
                first_ep = episodes[0]
                ref_w, ref_h = self.encoder.even(first_ep.width), self.encoder.even(first_ep.height)
            elif "x" in self.config.canvas.lower():
                w, h = self.config.canvas.lower().split("x")
                ref_w, ref_h = self.encoder.even(int(w)), self.encoder.even(int(h))
            else:
                raise ValueError("--canvas 需要 'first' 或 'WxH'")
            project.reference_resolution = (ref_w, ref_h)
        else:
            # Auto-detect most common resolution
            sizes = []
            for ep in episodes:
                if ep.width and ep.height:
                    sizes.append((self.encoder.even(ep.width), self.encoder.even(ep.height)))
            if sizes:
                ref_w, ref_h = Counter(sizes).most_common(1)[0][0]
                project.reference_resolution = (ref_w, ref_h)
        
        # Determine target FPS
        episode_paths = [str(ep.file_path) for ep in episodes]
        target_fps = self.encoder.choose_output_fps(
            episode_paths, self.config.target_fps, self.config.smart_fps
        )
        project.target_fps = target_fps
        
        # Set tail video if configured
        if self.config.tail_file:
            tail_path = Path(self.config.tail_file)
            # Handle relative path relative to project root
            if not tail_path.is_absolute():
                # Find project root by looking for assets directory
                current_dir = Path(__file__).parent
                while current_dir != current_dir.parent:
                    if (current_dir / "assets").exists():
                        tail_path = current_dir / self.config.tail_file
                        break
                    current_dir = current_dir.parent
                else:
                    # Fallback: relative to current working directory
                    tail_path = Path.cwd() / self.config.tail_file
            
            if tail_path.exists():
                project.tail_video = tail_path
                logger.info(f"設置尾部視頻：{tail_path}")
            else:
                logger.warning(f"尾部視頻文件不存在：{tail_path}")
        
        # Cover image logic removed
        
        return project
    
    def prepare_project_output_dir(self, project: DramaProject, exports_root: str, drama_date: Optional[str] = None) -> Tuple[str, Optional[str], int, int]:
        """Prepare output directory and determine how many materials to generate.
        
        Args:
            project: Drama project
            exports_root: Base export directory  
            drama_date: Optional specific date for this drama (format: "9.6")
        """
        drama_name = project.name
        
        # Use drama-specific date if provided, otherwise fall back to config date
        date_str = drama_date or self.config.date_str
        
        # Check if this is an explicit include (fresh run) or continuation
        if self.config.include and drama_name in self.config.include:
            # Fresh run - create new directory
            out_dir, run_suffix = prepare_export_dir(exports_root, drama_name, date_str)
            start_index = 1
            total_to_make = self.config.count
        else:
            # Check for existing materials and potentially continue
            latest_dir, run_suffix = get_latest_export_dir(exports_root, drama_name, date_str)
            if latest_dir:
                existing_count = count_existing_materials(latest_dir)
                if existing_count >= self.config.count:
                    logger.info(f"Skipping {drama_name}: already has {existing_count} materials")
                    return None, None, 0, 0
                
                # Continue in existing directory
                out_dir = latest_dir
                start_index = existing_count + 1
                total_to_make = self.config.count - existing_count
                logger.info(f"Continuing {drama_name}: {existing_count} existing, making {total_to_make} more")
            else:
                # Create new directory
                out_dir = os.path.join(exports_root, drama_name)
                os.makedirs(out_dir, exist_ok=True)
                run_suffix = None
                start_index = 1
                total_to_make = self.config.count
        
        return out_dir, run_suffix, start_index, total_to_make
    
    def generate_start_points(self, project: DramaProject, count: int) -> List[Tuple[int, float]]:
        """Generate start points for material generation."""
        if not project.episodes:
            return []
        
        starts = []
        num_episodes = len(project.episodes)
        
        if self.config.random_start:
            # Random start points
            for _ in range(count):
                ep_idx = random.randrange(num_episodes)
                episode = project.episodes[ep_idx]
                if episode.duration:
                    max_offset = min(60.0, episode.duration / 3.0)
                    offset = round(random.uniform(0, max_offset), 3)
                else:
                    offset = 0.0
                starts.append((ep_idx, offset))
        else:
            # Evenly distributed starts
            step = max(1, num_episodes // max(1, count))
            for i in range(count):
                ep_idx = min(i * step, num_episodes - 1)
                starts.append((ep_idx, 0.0))
        
        return starts
    
    def process_single_material(self, project: DramaProject, material_idx: int, 
                              start_ep_idx: int, start_offset: float, 
                              output_path: str, temp_root: str,
                              run_suffix: Optional[str], material_total: int) -> float:
        """Process a single material - equivalent to build_one_material."""
        start_time = time.time()
        
        logger.info(f"🎬 开始素材 | 剧：{project.name} | 第 {material_idx} / {material_total} 条")
        
        # Get episode paths
        episode_paths = [str(ep.file_path) for ep in project.episodes]
        ref_w, ref_h = project.reference_resolution or (1920, 1080)
        target_fps = project.target_fps or self.config.target_fps
        fontfile = self.config.get_default_font()
        
        # Use encoder to process material
        result_path = self.encoder.process_material(
            episodes=episode_paths,
            drama_name=project.name,
            start_ep_idx=start_ep_idx,
            start_offset=start_offset,
            min_sec=self.config.min_duration,
            max_sec=self.config.max_duration,
            out_path=output_path,
            reference_resolution=(ref_w, ref_h),
            target_fps=target_fps,
            fontfile=fontfile,
            footer_text=self.config.footer_text,
            side_text=self.config.side_text,
            use_hw=self.config.use_hardware,
            tail_video=project.tail_video,
            cover_image=None,
            temp_root=temp_root,
            keep_temp=self.config.keep_temp,
            tail_cache_dir=self.config.tail_cache_dir,
            refresh_tail_cache=self.config.refresh_tail_cache,
            material_idx=material_idx,
            material_total=material_total,
            fast_mode=self.config.fast_mode,
            filter_threads=self.config.filter_threads
        )
        
        processing_time = time.time() - start_time
        return processing_time
    
    def process_project_materials(self, project: DramaProject, out_dir: str, 
                                run_suffix: Optional[str], start_index: int, 
                                total_to_make: int, temp_root: str, drama_date: Optional[str] = None) -> Tuple[int, float]:
        """Process all materials for a project.
        
        Args:
            project: Drama project
            out_dir: Output directory
            run_suffix: Optional run suffix
            start_index: Starting material index
            total_to_make: Number of materials to make
            temp_root: Temporary directory root
            drama_date: Optional specific date for this drama (format: "9.6")
        """
        if total_to_make <= 0:
            return 0, 0.0
        
        project_start_time = time.time()
        
        # Generate start points
        start_points = self.generate_start_points(project, total_to_make)
        
        # Use drama-specific date if provided, otherwise fall back to config date
        date_str = drama_date or self.config.get_date_str()
        
        # Prepare tasks
        tasks = []
        def process_task(idx2: int, ep_idx: int, offset: float, output_path: str):
            try:
                dt = self.process_single_material(
                    project, idx2, ep_idx, offset, output_path, temp_root,
                    run_suffix, start_index + total_to_make - 1
                )
                return (idx2, None, dt, output_path)
            except Exception as e:
                return (idx2, e, 0.0, output_path)
        
        # Execute processing
        completed_count = 0
        if self.config.jobs == 1:
            # Sequential processing
            for i, (ep_idx, offset) in enumerate(start_points):
                material_idx = start_index + i
                base_name = f"{date_str}-{project.name}-xh-{material_idx:02d}"
                if run_suffix:
                    base_name += f"-{run_suffix}"
                output_path = os.path.join(out_dir, base_name + ".mp4")
                
                task_idx, error, dt, path = process_task(material_idx, ep_idx, offset, output_path)
                if error:
                    logger.error(f"Material {task_idx} failed: {error}")
                else:
                    completed_count += 1
                    remain = total_to_make - (i + 1)
                    # Get video duration for display
                    try:
                        duration = probe_duration(path)
                        duration_str = human_duration(duration)
                    except Exception:
                        duration_str = "未知"
                    logger.info(f"✅ 素材完成 | 剧：{project.name} | 第 {task_idx} 条 | 时长 {duration_str} | 用时 {human_duration(dt)} | 该剧剩余素材：{remain} 条")
        
        else:
            # Parallel processing
            with ThreadPoolExecutor(max_workers=self.config.jobs) as executor:
                futures = []
                for i, (ep_idx, offset) in enumerate(start_points):
                    material_idx = start_index + i
                    base_name = f"{date_str}-{project.name}-xh-{material_idx:02d}"
                    if run_suffix:
                        base_name += f"-{run_suffix}"
                    output_path = os.path.join(out_dir, base_name + ".mp4")
                    
                    future = executor.submit(process_task, material_idx, ep_idx, offset, output_path)
                    futures.append(future)
                
                # Collect results
                for future in as_completed(futures):
                    task_idx, error, dt, path = future.result()
                    if error:
                        logger.error(f"Material {task_idx} failed: {error}")
                    else:
                        completed_count += 1
                        remain = total_to_make - completed_count
                        # Get video duration for display
                        try:
                            duration = probe_duration(path)
                            duration_str = human_duration(duration)
                        except Exception:
                            duration_str = "未知"
                        logger.info(f"✅ 素材完成 | 剧：{project.name} | 第 {task_idx} 条 | 时长 {duration_str} | 用时 {human_duration(dt)} | 该剧剩余素材：{remain} 条")
        
        project_time = time.time() - project_start_time
        logger.info(f"📦 本剧完成 | {project.name} | 本轮生成 {completed_count}/{total_to_make} 条 | 用时 {human_duration(project_time)}")
        
        return completed_count, project_time
    
    def process_all_dramas(self, root_dir: str, drama_dates: Optional[Dict[str, str]] = None) -> Tuple[int, int]:
        """
        Process all dramas - main entry point equivalent to main() in dramas_process.py.
        
        Args:
            root_dir: 根目录路径
            drama_dates: 可选的剧目日期映射，格式为 {剧名: 日期字符串}
        """
        overall_start_time = time.time()
        
        # 创建历史记录会话
        command_line = " ".join(sys.argv)
        session = self.history_manager.create_session(self.config, command_line)
        
        # Set up exports directory
        exports_root = self.config.output_dir
        if not os.path.isabs(exports_root):
            exports_root = os.path.join(root_dir, "exports")
        
        # Handle date-based directory structure
        # If we have drama_dates mapping, we'll create date-specific directories later
        # Otherwise use the config date as before
        if drama_dates:
            # When using drama-specific dates, use the base exports_root
            actual_exports_root = exports_root
        else:
            # Use the original logic for backward compatibility
            actual_exports_root = exports_root
            if self.config.date_str:
                parent_dir = os.path.dirname(os.path.abspath(exports_root))
                actual_exports_root = os.path.join(parent_dir, f"{self.config.date_str}导出")
        
        os.makedirs(actual_exports_root, exist_ok=True)
        
        # Set up temporary directory
        temp_root = ensure_temp_root(self.config.temp_dir)
        
        # Discover dramas
        all_drama_dirs = self.scan_and_discover_dramas(root_dir)
        if not all_drama_dirs:
            logger.warning("No drama directories found")
            return 0, 0
        
        # Filter dramas based on config
        drama_dirs = self.filter_dramas_by_config(all_drama_dirs)
        if not drama_dirs:
            logger.warning("No dramas selected for processing")
            return 0, 0
        
        # Sort dramas by date if drama_dates is provided
        if drama_dates:
            def get_drama_sort_key(drama_dir: str) -> tuple:
                """获取剧目排序键值，用于按日期排序"""
                drama_name = os.path.basename(drama_dir.rstrip("/"))
                drama_date = drama_dates.get(drama_name, "9999.12.31")  # 默认值确保无日期的排在最后
                
                # 解析日期字符串为可排序的格式
                try:
                    # 处理 "M.D" 格式，如 "9.6" -> (9, 6)
                    if "." in drama_date:
                        month, day = drama_date.split(".", 1)
                        return (int(month), int(day), drama_name)
                    # 处理其他格式，暂时按字符串排序
                    else:
                        return (999, 999, drama_date, drama_name)
                except (ValueError, AttributeError):
                    # 解析失败，排在最后
                    return (999, 999, drama_date, drama_name)
            
            # 按日期排序剧目
            drama_dirs.sort(key=get_drama_sort_key)
            
            # 记录排序结果
            if logger.isEnabledFor(logging.INFO):
                logger.info("📅 按日期排序处理剧目:")
                for drama_dir in drama_dirs:
                    drama_name = os.path.basename(drama_dir.rstrip("/"))
                    drama_date = drama_dates.get(drama_name, "未知日期")
                    logger.info(f"  - {drama_name} (日期: {drama_date})")
        
        # Send start notification
        if self.feishu_notifier:
            try:
                dramas_info = []
                for drama_dir in drama_dirs:
                    drama_name = os.path.basename(drama_dir.rstrip("/"))
                    # 使用传入的日期信息，如果没有则使用配置中的日期
                    start_drama_date = drama_dates.get(drama_name) if drama_dates else self.config.get_date_str()
                    dramas_info.append({
                        'name': drama_name,
                        'date': start_drama_date,
                        'status': '待剪辑'
                    })
                
                self.feishu_notifier.send_start_notification(dramas_info, self.config)
                logger.info("已发送开始剪辑通知到飞书群")
            except Exception as e:
                logger.warning(f"发送开始通知失败: {e}")
        
        # Process each drama
        total_materials_planned = 0
        total_materials_done = 0
        successful_dramas = []  # Track successful processing results
        
        for drama_dir in drama_dirs:
            drama_start_time = time.time()  # 记录单个剧目开始时间
            
            try:
                # Create project
                project = self.create_drama_project(drama_dir)
                
                if not project.episodes:
                    logger.warning(f"Skipping {project.name}: no episodes found")
                    continue
                
                # Get drama-specific date if available
                drama_date = drama_dates.get(project.name) if drama_dates else None
                
                # Determine the export directory for this drama
                if drama_date and drama_dates:
                    # Create date-specific export directory
                    parent_dir = os.path.dirname(os.path.abspath(actual_exports_root))
                    date_export_dir = os.path.join(parent_dir, f"{drama_date}导出")
                    os.makedirs(date_export_dir, exist_ok=True)
                    drama_export_root = date_export_dir
                else:
                    # Use the common export directory
                    drama_export_root = actual_exports_root
                
                # Prepare output directory
                result = self.prepare_project_output_dir(project, drama_export_root, drama_date)
                if result[0] is None:  # Skip this drama
                    continue
                
                out_dir, run_suffix, start_index, total_to_make = result
                total_materials_planned += total_to_make
                
                # Update status to "剪辑中" when starting processing
                if self.status_callback:
                    try:
                        self.status_callback(project.name, "剪辑中")
                        logger.info(f"📝 已更新 '{project.name}' 状态为'剪辑中'")
                    except Exception as e:
                        logger.warning(f"⚠️ 更新 '{project.name}' 状态为'剪辑中'失败: {e}")
                
                # Log project info
                ref_w, ref_h = project.reference_resolution or (1920, 1080)
                logger.info(
                    f"=== {project.name} | 参考画布：{ref_w}x{ref_h} | "
                    f"输出FPS：{project.target_fps} | 运行批次：{run_suffix or '首次'} | "
                    f"计划生成：{total_to_make} 条，每条 {self.config.min_duration}~{self.config.max_duration}s ==="
                )
                
                # Process materials
                completed, project_time = self.process_project_materials(
                    project, out_dir, run_suffix, start_index, total_to_make, temp_root, drama_date
                )
                total_materials_done += completed
                
                drama_end_time = time.time()  # 记录单个剧目结束时间
                drama_total_time = drama_end_time - drama_start_time  # 计算剧目总耗时
                
                # Record successful processing details
                if completed > 0:
                    # Update status to "待上传" when processing is completed successfully
                    if self.status_callback:
                        try:
                            self.status_callback(project.name, "待上传")
                            logger.info(f"📝 已更新 '{project.name}' 状态为'待上传'")
                        except Exception as e:
                            logger.warning(f"⚠️ 更新 '{project.name}' 状态为'待上传'失败: {e}")
                    
                    # 构建素材文件路径列表
                    materials_list = []
                    if os.path.exists(out_dir):
                        for file in os.listdir(out_dir):
                            if file.endswith(('.mp4', '.mov', '.avi')):
                                materials_list.append(os.path.join(out_dir, file))
                    
                    drama_info = {
                        'name': project.name,
                        'completed': completed,
                        'planned': total_to_make,
                        'output_dir': out_dir,
                        'date': drama_date or self.config.get_date_str(),
                        'run_suffix': run_suffix,
                        'source_path': drama_dir,
                        'materials': materials_list,
                        'total_duration': sum(ep.duration or 0 for ep in project.episodes),
                        'duration_per_material': (self.config.min_duration + self.config.max_duration) / 2,
                        'start_time': drama_start_time,
                        'end_time': drama_end_time,
                        'processing_time': drama_total_time  # 总体时间（包含准备、处理、整理）
                    }
                    
                    successful_dramas.append(drama_info)
                    
                    # 添加到历史记录（使用总体时间）
                    self.history_manager.add_drama_record(session, drama_info, self.config, drama_total_time)
                
                # 即使没有成功，也记录开始时间用于统计
                elif total_to_make > 0:
                    # 失败的剧目也记录到历史中
                    drama_info = {
                        'name': project.name,
                        'completed': 0,
                        'planned': total_to_make,
                        'output_dir': out_dir,
                        'date': drama_date or self.config.get_date_str(),
                        'run_suffix': run_suffix,
                        'source_path': drama_dir,
                        'materials': [],
                        'total_duration': sum(ep.duration or 0 for ep in project.episodes),
                        'duration_per_material': 0,
                        'start_time': drama_start_time,
                        'end_time': drama_end_time,
                        'processing_time': drama_total_time
                    }
                    
                    self.history_manager.add_drama_record(session, drama_info, self.config, drama_total_time)
                
            except Exception as e:
                logger.error(f"Failed to process drama {os.path.basename(drama_dir)}: {e}")
                continue
        
        # Final summary
        overall_time = time.time() - overall_start_time
        logger.info(f"🎯 全部完成。输出根目录：{actual_exports_root} | 总计 {total_materials_done}/{total_materials_planned} 条 | 总用时 {human_duration(overall_time)}")
        
        # Send completion notification
        if self.feishu_notifier:
            try:
                # 构建剧目结果信息
                dramas_results = []
                for drama_info in successful_dramas:
                    dramas_results.append({
                        'name': drama_info['name'],
                        'date': drama_info['date'],
                        'status': '待上传',
                        'completed': drama_info['completed'],
                        'planned': drama_info['planned'],
                        'output_dir': drama_info['output_dir']
                    })
                
                # 添加失败的剧目信息（如果有的话）
                processed_names = {d['name'] for d in successful_dramas}
                for drama_dir in drama_dirs:
                    drama_name = os.path.basename(drama_dir.rstrip("/"))
                    if drama_name not in processed_names:
                        # Get drama-specific date if available
                        failed_drama_date = drama_dates.get(drama_name) if drama_dates else None
                        dramas_results.append({
                            'name': drama_name,
                            'date': failed_drama_date or self.config.get_date_str(),
                            'status': '失败',
                            'completed': 0,
                            'planned': self.config.count,
                            'output_dir': ''
                        })
                
                self.feishu_notifier.send_completion_notification(
                    dramas_results, total_materials_done, total_materials_planned, overall_time
                )
                logger.info("已发送完成剪辑通知到飞书群")
            except Exception as e:
                logger.warning(f"发送完成通知失败: {e}")
        
        # 完成历史记录会话
        self.history_manager.finish_session(session)
        
        # Print detailed completion summary
        self._print_completion_summary(successful_dramas, actual_exports_root)
        
        # 显示历史记录保存信息
        if successful_dramas:
            history_dir = self.history_manager.base_dir
            logger.info(f"📝 处理历史已保存到：{history_dir}")
        
        return total_materials_done, total_materials_planned
    
    def _print_completion_summary(self, successful_dramas: List[dict], actual_exports_root: str) -> None:
        """Print detailed completion summary for all successfully processed dramas."""
        if not successful_dramas:
            logger.info("📋 没有成功处理的短剧")
            return
        
        logger.info("=" * 80)
        logger.info("📋 剪辑完成汇总")
        logger.info("=" * 80)
        
        for i, drama in enumerate(successful_dramas, 1):
            name = drama['name']
            completed = drama['completed']
            planned = drama['planned']
            output_dir = drama['output_dir']
            date = drama['date']
            run_suffix = drama['run_suffix']
            processing_time = drama.get('processing_time', 0)
            
            # Format drama info
            status = "✅ 完成" if completed == planned else f"⚠️ 部分完成 ({completed}/{planned})"
            suffix_info = f" ({run_suffix})" if run_suffix else ""
            
            logger.info(f"{i:2d}. 剧名: {name}")
            logger.info(f"    状态: {status}")
            logger.info(f"    日期: {date}{suffix_info}")
            logger.info(f"    素材: {completed} 条")
            logger.info(f"    耗时: {human_duration(processing_time)}")
            logger.info(f"    目录: {output_dir}")
            logger.info("")
        
        # Summary statistics
        total_dramas = len(successful_dramas)
        total_materials = sum(d['completed'] for d in successful_dramas)
        fully_completed = sum(1 for d in successful_dramas if d['completed'] == d['planned'])
        total_processing_time = sum(d.get('processing_time', 0) for d in successful_dramas)
        
        logger.info(f"📊 统计信息:")
        logger.info(f"   • 成功处理短剧: {total_dramas} 部")
        logger.info(f"   • 完全完成短剧: {fully_completed} 部")
        logger.info(f"   • 生成素材总计: {total_materials} 条")
        logger.info(f"   • 总耗时: {human_duration(total_processing_time)}")
        logger.info(f"   • 导出根目录: {actual_exports_root}")
        logger.info("=" * 80)