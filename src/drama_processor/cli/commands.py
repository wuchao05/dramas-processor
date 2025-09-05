"""CLI command implementations."""

import logging
import os
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import click

from ..config import ConfigManager, save_config
from ..core.processor import DramaProcessor
from ..models.config import ProcessingConfig
from ..models.project import DramaProject
from ..utils.system import ensure_dir
from ..utils.history import HistoryManager


logger = logging.getLogger(__name__)


@click.command("process")
@click.argument("root_dir", type=click.Path(exists=True, file_okay=False, path_type=Path), required=False)
# Material generation settings
@click.option("--count", type=int, default=10, help="每部短剧生成素材条数量（默认10）")
@click.option("--min-sec", type=float, default=480, help="每条素材最小时长（默认480s=8分钟）")
@click.option("--max-sec", type=float, default=900, help="每条素材最大时长（默认900s=15分钟）")
@click.option("--date", type=str, default=None, help="文件名前缀日期，如 8.26；默认当天")

# Random start settings
@click.option("--random-start/--no-random-start", default=True, help="随机起点，提升多样性（默认开启）")
@click.option("--seed", type=int, default=None, help="随机起点种子；不传则每次运行都会不同")

# Video settings
@click.option("--sw", is_flag=True, help="使用软编(libx264)；默认硬编(h264_videotoolbox)")
@click.option("--fps", type=int, default=60, help="输出帧率（默认60）")
@click.option("--smart-fps/--no-smart-fps", default=True, help="自适应帧率：源<40fps 用源帧率，否则封顶45fps（默认开启）")
@click.option("--canvas", type=str, default=None, help="参考画布：'WxH' 或 'first'；默认自动选择最常见分辨率")

# Text settings
@click.option("--font-file", type=str, default=None, help="中文字体文件路径")
@click.option("--footer-text", type=str, default="热门短剧 休闲必看", help="底部居中文案")
@click.option("--side-text", type=str, default="剧情纯属虚构 请勿模仿", help="右上竖排文案（可横排传入，脚本会自动竖排化）")

# Tail settings
@click.option("--tail-file", type=str, default=None, help="尾部引导视频路径（默认脚本同级 tail.mp4；不存在则跳过）")

# Cover settings - REMOVED

# Selection settings
@click.option("--include", multiple=True, help="仅处理指定短剧名（可多次传或用逗号/换行分隔）")
@click.option("--exclude", multiple=True, help="排除指定短剧名（可多次传或用逗号/换行分隔）")
@click.option("--full", is_flag=True, help="全量扫描当前根目录下的所有短剧")
@click.option("--no-interactive", is_flag=True, help="禁用交互式选择（默认在未指定 include/exclude/full 且在 TTY 下会交互选择）")

# Performance settings
@click.option("--jobs", type=int, default=1, help="每部剧内的并发生成数（默认1；建议2~4）")

# Directory settings
@click.option("--temp-dir", type=str, default=None, help="临时工作目录根（默认 /tmp）")
@click.option("--keep-temp", is_flag=True, help="保留临时目录，便于调试（默认不保留）")
@click.option("--out-dir", type=str, default="../导出素材", help="自定义导出目录（默认 ../导出素材）")

# Tail cache settings
@click.option("--tail-cache-dir", type=str, default="/tmp/tails_cache", help="尾部规范化缓存目录（默认 /tmp/tails_cache）")
@click.option("--refresh-tail-cache", is_flag=True, help="强制刷新尾部缓存")

# Processing optimizations
@click.option("--fast-mode", is_flag=True, help="更快：关闭 eq/hue 随机色彩扰动，仅保留缩放/裁切/填充与文字")
@click.option("--filter-threads", type=int, default=max(2, (os.cpu_count() or 4)//2), help="滤镜并行线程数（默认=CPU核数一半，至少2）")
@click.option("--verbose", is_flag=True, help="详细日志：显示完整的FFmpeg命令和更多调试信息")

@click.pass_context
def process_command(
    ctx,
    root_dir: Optional[Path],
    # Material generation
    count: int,
    min_sec: float,
    max_sec: float,
    date: Optional[str],
    # Random start
    random_start: bool,
    seed: Optional[int],
    # Video settings
    sw: bool,
    fps: int,
    smart_fps: bool,
    canvas: Optional[str],
    # Text settings
    font_file: Optional[str],
    footer_text: str,
    side_text: str,
    # Tail settings
    tail_file: Optional[str],

    # Selection settings
    include: Tuple[str],
    exclude: Tuple[str],
    full: bool,
    no_interactive: bool,
    # Performance
    jobs: int,
    # Directories
    temp_dir: Optional[str],
    keep_temp: bool,
    out_dir: str,
    # Tail cache
    tail_cache_dir: str,
    refresh_tail_cache: bool,
    # Optimizations
    fast_mode: bool,
    filter_threads: int,
    verbose: bool,
):
    """批量遍历根目录短剧并产出素材（集尾对齐/尾部缓存/交互多选/临时目录可控/计时日志增强/提速选项）"""
    
    # Handle default source directory
    if root_dir is None:
        # Get the base config to access source directories
        config_obj = ctx.obj.get("config") or ProcessingConfig()
        actual_dir = Path(config_obj.get_actual_source_dir())
        
        if not actual_dir.exists():
            click.echo(f"错误：主目录和备份目录都不存在：", err=True)
            click.echo(f"  主目录：{config_obj.default_source_dir}", err=True)
            click.echo(f"  备份目录：{config_obj.backup_source_dir}", err=True)
            click.echo("请确保至少一个目录存在，或指定一个有效的源目录路径", err=True)
            sys.exit(1)
        
        root_dir = actual_dir
        
        # Directory usage info removed to keep output clean
    
    # Validate parameters
    if min_sec <= 0 or max_sec <= 0 or min_sec > max_sec:
        click.echo("参数错误：请保证 0 < --min-sec <= --max-sec。", err=True)
        sys.exit(2)
    
    # Expand include/exclude lists that may contain comma-separated or newline-separated values
    include_list = []
    for item in include:
        # First split by newlines, then by commas
        for line in item.split('\n'):
            include_list.extend([s.strip() for s in line.split(",") if s.strip()])
    
    # Check for duplicates in include list and auto-deduplicate
    if include_list:
        original_count = len(include_list)
        duplicates = []
        seen = set()
        deduplicated_list = []
        
        for drama_name in include_list:
            if drama_name in seen:
                duplicates.append(drama_name)
            else:
                seen.add(drama_name)
                deduplicated_list.append(drama_name)
        
        if duplicates:
            click.echo(f"⚠️  检测到重复的剧名：{', '.join(duplicates)}")
            click.echo(f"已自动去重：{original_count} → {len(deduplicated_list)} 部剧")
        
        include_list = deduplicated_list
    
    exclude_list = []
    for item in exclude:
        # First split by newlines, then by commas
        for line in item.split('\n'):
            exclude_list.extend([s.strip() for s in line.split(",") if s.strip()])
    
    # Check for duplicates in exclude list and auto-deduplicate
    if exclude_list:
        original_count = len(exclude_list)
        duplicates = []
        seen = set()
        deduplicated_list = []
        
        for drama_name in exclude_list:
            if drama_name in seen:
                duplicates.append(drama_name)
            else:
                seen.add(drama_name)
                deduplicated_list.append(drama_name)
        
        if duplicates:
            click.echo(f"⚠️  排除列表中检测到重复的剧名：{', '.join(duplicates)}")
            click.echo(f"已自动去重：{original_count} → {len(deduplicated_list)} 部剧")
        
        exclude_list = deduplicated_list
    
    # Adjust output directory based on actual source directory if using default out_dir
    adjusted_out_dir = out_dir
    if out_dir == "../导出素材" and root_dir:  # Using default out_dir and have resolved source directory
        # Always adjust export base directory based on actual source directory used
        config_obj = ctx.obj.get("config") or ProcessingConfig()
        export_base = config_obj.get_export_base_dir()
        adjusted_out_dir = os.path.join(export_base, "导出素材")
        
        # Export directory adjustment info removed to keep output clean
    
    # Create configuration
    config = ProcessingConfig(
        # Basic settings
        target_fps=fps,
        smart_fps=smart_fps,
        fast_mode=fast_mode,
        filter_threads=filter_threads,
        verbose=verbose,
        
        # Duration settings
        min_duration=min_sec,
        max_duration=max_sec,
        
        # Material generation
        count=count,
        date_str=date,
        
        # Text overlay settings
        footer_text=footer_text,
        side_text=side_text,
        font_file=font_file,
        
        # Processing settings
        random_start=random_start,
        seed=seed,
        use_hardware=not sw,  # Invert --sw flag
        keep_temp=keep_temp,
        jobs=jobs,
        
        # Canvas/Resolution
        canvas=canvas,
        
        # Directory settings
        default_source_dir=str(root_dir),  # Save the resolved source directory
        temp_dir=temp_dir,
        output_dir=adjusted_out_dir,
        tail_cache_dir=tail_cache_dir,
        refresh_tail_cache=refresh_tail_cache,
        
        # Selection settings
        include=include_list if include_list else None,
        exclude=exclude_list if exclude_list else None,
        full=full,
        no_interactive=no_interactive,
        

    )
    
    # Handle tail file and update config
    if tail_file:
        # Explicit tail file
        if os.path.isfile(tail_file):
            config.tail_file = tail_file
        else:
            click.echo(f"⚠️ 指定的尾部文件不存在：{tail_file}")
            config.tail_file = None
    else:
        # Check for tail.mp4 in assets directory (new structure)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        default_tail = os.path.join(project_root, "assets", "tail.mp4")
        if os.path.isfile(default_tail):
            config.tail_file = default_tail
        elif config.tail_file:
            # Check if the config file tail_file path exists relative to project root
            config_tail_path = os.path.join(project_root, config.tail_file) if not os.path.isabs(config.tail_file) else config.tail_file
            if not os.path.isfile(config_tail_path):
                click.echo(f"⚠️ 配置中的尾部文件不存在：{config_tail_path}")
                config.tail_file = None
    
    # Initialize processor
    processor = DramaProcessor(config)
    
    # Main processing
    try:
        total_done, total_planned = processor.process_all_dramas(str(root_dir))
        
        if total_planned == 0:
            click.echo("没有找到需要处理的短剧。")
            sys.exit(0)
        
        click.echo(f"处理完成：{total_done}/{total_planned} 条素材生成成功")
        
        if total_done < total_planned:
            sys.exit(1)  # Partial failure
        
    except KeyboardInterrupt:
        click.echo("\n用户中断操作", err=True)
        sys.exit(130)
    except Exception as e:
        click.echo(f"处理失败：{e}", err=True)
        if ctx.obj.get("debug"):
            import traceback
            traceback.print_exc()
        sys.exit(1)


@click.command("analyze")
@click.argument("root_dir", type=click.Path(exists=True, file_okay=False, path_type=Path), required=False)
@click.option("--output", type=click.File("w"), default="-", help="Output file (default: stdout)")
@click.option("--format", type=click.Choice(["text", "json", "yaml"]), default="text", help="Output format")
@click.pass_context
def analyze_command(ctx, root_dir: Optional[Path], output, format: str):
    """分析短剧项目但不进行处理。"""
    
    # Handle default source directory
    if root_dir is None:
        config_obj = ctx.obj.get("config") or ProcessingConfig()
        default_dir = Path(config_obj.default_source_dir)
        
        if not default_dir.exists():
            click.echo(f"错误：默认源素材目录不存在：{default_dir}", err=True)
            click.echo("请指定一个有效的源目录路径，或检查配置文件中的 default_source_dir 设置", err=True)
            sys.exit(1)
        
        root_dir = default_dir
    
    config = ProcessingConfig()  # Use default config for analysis
    
    # Set analyzer mode to suppress FPS output
    import sys
    sys._drama_analyzer_mode = True
    
    # Initialize processor
    processor = DramaProcessor(config)
    
    # Discover dramas
    drama_dirs = processor.scan_and_discover_dramas(str(root_dir))
    
    if not drama_dirs:
        click.echo("未发现短剧目录")
        return
    
    # Analyze each drama
    results = []
    for drama_dir in drama_dirs:
        drama_name = os.path.basename(drama_dir.rstrip("/"))
        try:
            # Show progress
            click.echo(f"正在分析: {drama_name}...", err=True)
            project = processor.create_drama_project(drama_dir)
            results.append({
                "name": project.name,
                "path": str(project.source_dir),
                "episodes": len(project.episodes),
                "total_duration": project.total_duration,
                "reference_resolution": project.reference_resolution,
                "target_fps": project.target_fps,
                # Cover field removed
                "safe_episodes": project.safe_episodes_count,
                "unsafe_episodes": project.unsafe_episodes_count,
            })
            click.echo(f"✓ 完成分析: {drama_name}", err=True)
        except Exception as e:
            click.echo(f"✗ 分析 {drama_name} 失败: {e}", err=True)
            # 详细错误信息
            import traceback
            click.echo(f"详细错误: {traceback.format_exc()}", err=True)
    
    # Output results
    if format == "text":
        for result in results:
            output.write(f"\n短剧: {result['name']}\n")
            output.write(f"路径: {result['path']}\n")
            output.write(f"集数: {result['episodes']}\n")
            output.write(f"总时长: {result['total_duration']:.2f}秒\n")
            
            if result['reference_resolution']:
                w, h = result['reference_resolution']
                output.write(f"分辨率: {w}x{h}\n")
            
            if result['target_fps']:
                output.write(f"目标帧率: {result['target_fps']}\n")
            
            # Cover output removed
            output.write(f"安全集数: {result['safe_episodes']}\n")
            output.write(f"不安全集数: {result['unsafe_episodes']}\n")
    
    elif format == "json":
        import json
        json.dump(results, output, indent=2, ensure_ascii=False, default=str)
    
    elif format == "yaml":
        import yaml
        yaml.dump(results, output, default_flow_style=False, allow_unicode=True)


@click.group("config")
def config_command():
    """配置管理命令。"""
    pass


@config_command.command("show")
@click.pass_context
def show_config(ctx):
    """显示当前配置。"""
    config = ctx.obj.get("config") or ProcessingConfig()
    config_dict = config.dict()
    
    import yaml
    click.echo(yaml.dump(config_dict, default_flow_style=False, allow_unicode=True))


@config_command.command("generate")
@click.argument("output_file", type=click.Path(path_type=Path))
@click.pass_context
def generate_config(ctx, output_file: Path):
    """生成默认配置文件。"""
    config = ProcessingConfig()
    
    try:
        save_config(config, output_file)
        click.echo(f"配置已保存到: {output_file}")
    except Exception as e:
        click.echo(f"保存配置失败: {e}", err=True)
        sys.exit(1)


@config_command.command("validate")
@click.argument("config_file", type=click.Path(exists=True, path_type=Path))
def validate_config(config_file: Path):
    """验证配置文件。"""
    try:
        manager = ConfigManager()
        config = manager.load(config_file)
        click.echo("配置文件有效")
    except Exception as e:
        click.echo(f"配置验证失败: {e}", err=True)
        sys.exit(1)


# Legacy compatibility command that matches the original script exactly
@click.command("run", hidden=True)
@click.argument("root_dir", required=False)
@click.option("--count", type=int, default=10)
@click.option("--min-sec", type=float, default=480)
@click.option("--max-sec", type=float, default=900)
@click.option("--date", type=str, default=None)
@click.option("--random-start", is_flag=True, default=True)
@click.option("--seed", type=int, default=None)
@click.option("--sw", is_flag=True)
@click.option("--fps", type=int, default=60)
@click.option("--smart-fps", is_flag=True, default=True)
@click.option("--canvas", type=str, default=None)
@click.option("--font-file", type=str, default=None)
@click.option("--footer-text", type=str, default="热门短剧 休闲必看")
@click.option("--side-text", type=str, default="剧情纯属虚构 请勿模仿")
@click.option("--tail-file", type=str, default=None)
# Cover options removed
@click.option("--include", multiple=True)
@click.option("--exclude", multiple=True)
@click.option("--jobs", type=int, default=1)
@click.option("--full", is_flag=True)
@click.option("--no-interactive", is_flag=True)
@click.option("--temp-dir", type=str, default=None)
@click.option("--keep-temp", is_flag=True)
@click.option("--out-dir", type=str, default="../导出素材")
@click.option("--tail-cache-dir", type=str, default="/tmp/tails_cache")
@click.option("--refresh-tail-cache", is_flag=True)
@click.option("--fast-mode", is_flag=True)
@click.option("--filter-threads", type=int, default=max(2, (os.cpu_count() or 4)//2))
def legacy_run_command(**kwargs):
    """Legacy compatibility - same as process command."""
    # Convert to the process command format
    ctx = click.get_current_context()
    ctx.invoke(process_command, **kwargs)


# History management commands
@click.group("history")
def history_command():
    """查看和管理剪辑历史记录。"""
    pass


@history_command.command("recent")
@click.option("--limit", type=int, default=10, help="显示最近N次会话（默认10）")
def history_recent(limit: int):
    """查看最近的剪辑会话记录。"""
    history_manager = HistoryManager()
    
    try:
        sessions = history_manager.get_recent_sessions(limit)
        
        if not sessions:
            click.echo("📋 暂无剪辑历史记录")
            return
        
        click.echo("=" * 80)
        click.echo("📋 最近剪辑会话记录")
        click.echo("=" * 80)
        
        for i, session in enumerate(sessions, 1):
            duration = session.duration_minutes
            success_rate = session.success_rate * 100
            processing_time_hours = session.actual_processing_time / 3600
            efficiency = session.processing_efficiency_ratio * 100
            
            click.echo(f"\n{i:2d}. 会话ID: {session.session_id}")
            click.echo(f"    时间: {session.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
            click.echo(f"    会话持续: {duration:.1f} 分钟")
            click.echo(f"    实际处理: {processing_time_hours:.2f} 小时")
            click.echo(f"    处理效率: {efficiency:.1f}% (处理时间/会话时间)")
            click.echo(f"    处理: {session.successful_dramas}/{session.total_dramas} 部短剧 (成功率 {success_rate:.1f}%)")
            click.echo(f"    素材: {session.total_materials} 条，{session.total_size_mb:.1f} MB")
            click.echo(f"    命令: {session.command_line}")
            
            if session.dramas:
                click.echo(f"    短剧: {', '.join(d.name for d in session.dramas[:3])}")
                if len(session.dramas) > 3:
                    click.echo(f"          （还有 {len(session.dramas) - 3} 部...）")
                
                # 显示每部剧的处理时间
                click.echo(f"    耗时明细:")
                for drama in session.dramas[:5]:  # 只显示前5部
                    time_min = drama.processing_time / 60
                    click.echo(f"      - {drama.name}: {time_min:.1f} 分钟 ({drama.completed_count}/{drama.planned_count} 条)")
                if len(session.dramas) > 5:
                    click.echo(f"      ... 还有 {len(session.dramas) - 5} 部剧")
        
        click.echo("\n" + "=" * 80)
        
    except Exception as e:
        click.echo(f"❌ 获取历史记录失败: {e}", err=True)


@history_command.command("drama")
@click.argument("drama_name", type=str)
def history_drama(drama_name: str):
    """查看特定短剧的处理历史。"""
    history_manager = HistoryManager()
    
    try:
        drama_history = history_manager.get_drama_history(drama_name)
        
        if not drama_history:
            click.echo(f"📋 未找到短剧 '{drama_name}' 的处理历史")
            return
        
        click.echo("=" * 80)
        click.echo(f"📋 短剧 '{drama_name}' 处理历史")
        click.echo("=" * 80)
        
        total_materials = 0
        total_size = 0.0
        
        for i, record in enumerate(drama_history, 1):
            click.echo(f"\n{i:2d}. 日期: {record['date']}")
            click.echo(f"    会话: {record['session_id']}")
            click.echo(f"    状态: {'✅ 完成' if record['completed'] else '⚠️ 部分完成'}")
            click.echo(f"    素材: {record['materials_count']} 条，{record['size_mb']:.1f} MB")
            click.echo(f"    目录: {record['output_dir']}")
            click.echo(f"    用时: {record['processing_time']:.1f} 秒")
            
            if record.get('materials'):
                click.echo(f"    文件: {', '.join(record['materials'][:2])}")
                if len(record['materials']) > 2:
                    click.echo(f"          （还有 {len(record['materials']) - 2} 个文件...）")
            
            total_materials += record['materials_count']
            total_size += record['size_mb']
        
        click.echo(f"\n📊 统计信息:")
        click.echo(f"    总处理次数: {len(drama_history)} 次")
        click.echo(f"    总生成素材: {total_materials} 条")
        click.echo(f"    总文件大小: {total_size:.1f} MB")
        click.echo("=" * 80)
        
    except Exception as e:
        click.echo(f"❌ 获取剧目历史失败: {e}", err=True)


@history_command.command("stats")
def history_stats():
    """查看全时段统计信息。"""
    history_manager = HistoryManager()
    
    try:
        stats = history_manager.get_all_time_stats()
        
        if not stats:
            click.echo("📋 暂无统计数据")
            return
        
        click.echo("=" * 80)
        click.echo("📊 全时段统计信息")
        click.echo("=" * 80)
        
        click.echo(f"\n🕐 时间范围:")
        if stats.first_session:
            click.echo(f"    首次使用: {stats.first_session.strftime('%Y-%m-%d %H:%M:%S')}")
        if stats.last_session:
            click.echo(f"    最近使用: {stats.last_session.strftime('%Y-%m-%d %H:%M:%S')}")
        click.echo(f"    活跃天数: {stats.active_days} 天")
        
        click.echo(f"\n📈 处理统计:")
        click.echo(f"    总会话数: {stats.total_sessions} 次")
        click.echo(f"    总处理短剧: {stats.total_dramas} 部")
        click.echo(f"    成功处理: {stats.successful_dramas} 部 (成功率 {stats.success_rate * 100:.1f}%)")
        click.echo(f"    总生成素材: {stats.total_materials} 条")
        click.echo(f"    总文件大小: {stats.total_size_mb:.1f} MB ({stats.total_size_mb / 1024:.2f} GB)")
        
        click.echo(f"\n⏱️ 时长统计:")
        click.echo(f"    总处理时长: {stats.total_processing_hours:.1f} 小时")
        click.echo(f"    平均每会话: {stats.avg_dramas_per_session:.1f} 部短剧")
        
        if stats.total_dramas > 0:
            avg_time_per_drama = stats.total_processing_time / stats.total_dramas / 60  # 分钟
            click.echo(f"    平均每部剧: {avg_time_per_drama:.1f} 分钟")
        
        if stats.total_materials > 0:
            avg_time_per_material = stats.total_processing_time / stats.total_materials / 60  # 分钟
            click.echo(f"    平均每条素材: {avg_time_per_material:.1f} 分钟")
        
        if stats.active_days > 0:
            daily_processing_time = stats.total_processing_hours / stats.active_days
            click.echo(f"    日均处理时长: {daily_processing_time:.1f} 小时")
        
        click.echo(f"\n🎬 处理过的短剧:")
        click.echo(f"    总数: {len(stats.unique_dramas)} 部")
        if stats.unique_dramas:
            # 显示前10个短剧名
            displayed_dramas = stats.unique_dramas[:10]
            click.echo(f"    列表: {', '.join(displayed_dramas)}")
            if len(stats.unique_dramas) > 10:
                click.echo(f"          （还有 {len(stats.unique_dramas) - 10} 部...）")
        
        click.echo("=" * 80)
        
    except Exception as e:
        click.echo(f"❌ 获取统计信息失败: {e}", err=True)


# Feishu integration commands
@click.group("feishu")
def feishu_command():
    """飞书多维表格集成命令。"""
    pass


@feishu_command.command("list")
@click.option("--status", type=str, default="待剪辑", help="筛选状态（默认：待剪辑）")
@click.pass_context
def feishu_list(ctx, status: str):
    """查看飞书表格中的待处理剧目列表。"""
    config = ctx.obj.get("config") or ProcessingConfig()
    
    if not config.feishu:
        click.echo("❌ 飞书配置未设置，请在配置文件中添加飞书相关配置", err=True)
        sys.exit(1)
    
    try:
        from ..integrations.feishu_client import FeishuClient
        
        client = FeishuClient(config.feishu)
        dramas = client.get_pending_dramas(status_filter=status)
        
        if not dramas:
            click.echo(f"📋 未找到状态为 '{status}' 的剧目")
            return
        
        click.echo("=" * 60)
        click.echo(f"📋 飞书表格中状态为 '{status}' 的剧目")
        click.echo("=" * 60)
        
        for i, drama in enumerate(dramas, 1):
            click.echo(f"{i:2d}. {drama}")
        
        click.echo(f"\n📊 总计: {len(dramas)} 部剧")
        click.echo("=" * 60)
        
    except Exception as e:
        click.echo(f"❌ 查询飞书数据失败: {e}", err=True)
        if ctx.obj.get("debug"):
            import traceback
            traceback.print_exc()
        sys.exit(1)


@feishu_command.command("run")
@click.option("--status", type=str, default="待剪辑", help="筛选状态（默认：待剪辑）")
@click.argument("root_dir", type=click.Path(exists=True, file_okay=False, path_type=Path), required=False)
# Material generation settings
@click.option("--count", type=int, default=10, help="每部短剧生成素材条数量（默认10）")
@click.option("--min-sec", type=float, default=480, help="每条素材最小时长（默认480s=8分钟）")
@click.option("--max-sec", type=float, default=900, help="每条素材最大时长（默认900s=15分钟）")
@click.option("--date", type=str, default=None, help="文件名前缀日期，如 8.26；默认当天")
# Random start settings
@click.option("--random-start/--no-random-start", default=True, help="随机起点，提升多样性（默认开启）")
@click.option("--seed", type=int, default=None, help="随机起点种子；不传则每次运行都会不同")
# Video settings
@click.option("--sw", is_flag=True, help="使用软编(libx264)；默认硬编(h264_videotoolbox)")
@click.option("--fps", type=int, default=60, help="输出帧率（默认60）")
@click.option("--smart-fps/--no-smart-fps", default=True, help="自适应帧率：源<40fps 用源帧率，否则封顶45fps（默认开启）")
@click.option("--canvas", type=str, default=None, help="参考画布：'WxH' 或 'first'；默认自动选择最常见分辨率")
# Text settings
@click.option("--font-file", type=str, default=None, help="中文字体文件路径")
@click.option("--footer-text", type=str, default="热门短剧 休闲必看", help="底部居中文案")
@click.option("--side-text", type=str, default="剧情纯属虚构 请勿模仿", help="右上竖排文案（可横排传入，脚本会自动竖排化）")
# Tail settings
@click.option("--tail-file", type=str, default=None, help="尾部引导视频路径（默认脚本同级 tail.mp4；不存在则跳过）")
# Performance settings
@click.option("--jobs", type=int, default=1, help="每部剧内的并发生成数（默认1；建议2~4）")
# Directory settings
@click.option("--temp-dir", type=str, default=None, help="临时工作目录根（默认 /tmp）")
@click.option("--keep-temp", is_flag=True, help="保留临时目录，便于调试（默认不保留）")
@click.option("--out-dir", type=str, default="../导出素材", help="自定义导出目录（默认 ../导出素材）")
# Tail cache settings
@click.option("--tail-cache-dir", type=str, default="/tmp/tails_cache", help="尾部规范化缓存目录（默认 /tmp/tails_cache）")
@click.option("--refresh-tail-cache", is_flag=True, help="强制刷新尾部缓存")
# Processing optimizations
@click.option("--fast-mode", is_flag=True, help="更快：关闭 eq/hue 随机色彩扰动，仅保留缩放/裁切/填充与文字")
@click.option("--filter-threads", type=int, default=max(2, (os.cpu_count() or 4)//2), help="滤镜并行线程数（默认=CPU核数一半，至少2）")
@click.option("--verbose", is_flag=True, help="详细日志：显示完整的FFmpeg命令和更多调试信息")
@click.pass_context  
def feishu_run(ctx, status: str, root_dir: Optional[Path],
    # Material generation
    count: int, min_sec: float, max_sec: float, date: Optional[str],
    # Random start
    random_start: bool, seed: Optional[int],
    # Video settings
    sw: bool, fps: int, smart_fps: bool, canvas: Optional[str],
    # Text settings
    font_file: Optional[str], footer_text: str, side_text: str,
    # Tail settings
    tail_file: Optional[str],
    # Performance
    jobs: int,
    # Directories
    temp_dir: Optional[str], keep_temp: bool, out_dir: str,
    # Tail cache
    tail_cache_dir: str, refresh_tail_cache: bool,
    # Optimizations
    fast_mode: bool, filter_threads: int, verbose: bool):
    """一键查询飞书表格中的剧目并自动剪辑，自动更新状态。"""
    config = ctx.obj.get("config") or ProcessingConfig()
    
    if not config.feishu:
        click.echo("❌ 飞书配置未设置，请在配置文件中添加飞书相关配置", err=True)
        sys.exit(1)
    
    try:
        from ..integrations.feishu_client import FeishuClient, _convert_date_format
        
        client = FeishuClient(config.feishu)
        
        # 转换日期格式（如果指定了date参数）
        feishu_date_filter = None
        if date:
            try:
                feishu_date_filter = _convert_date_format(date)
                click.echo(f"📅 日期过滤: {date} -> {feishu_date_filter}")
            except ValueError as e:
                click.echo(f"⚠️ 日期格式转换失败: {e}", err=True)
                click.echo("将忽略日期过滤条件，继续处理...")
        
        # 获取剧名和对应的记录ID
        drama_records = client.get_pending_dramas_with_records(status_filter=status, date_filter=feishu_date_filter)
        dramas = list(drama_records.keys())
        
        # 更新显示的过滤条件描述
        filter_desc = f"状态为 '{status}'"
        if feishu_date_filter:
            filter_desc += f" 且日期为 '{feishu_date_filter}'"
        
        if not dramas:
            click.echo(f"📋 未找到{filter_desc}的剧目")
            return
        
        click.echo("=" * 60)
        click.echo(f"📋 从飞书获取到 {len(dramas)} 部待处理剧目")
        click.echo("=" * 60)
        
        for i, drama in enumerate(dramas, 1):
            click.echo(f"{i:2d}. {drama}")
        
        # 确认处理
        if not click.confirm(f"\n确认要自动剪辑这 {len(dramas)} 部剧吗？（状态将自动更新）"):
            click.echo("取消处理")
            return
        
        # 更新配置以包含传入的参数
        config.include = dramas
        config.full = False
        config.no_interactive = True  # 禁用交互式选择
        
        # Handle default source directory
        if root_dir is None:
            actual_dir = Path(config.get_actual_source_dir())
            
            if not actual_dir.exists():
                click.echo(f"错误：主目录和备份目录都不存在：", err=True)
                click.echo(f"  主目录：{config.default_source_dir}", err=True)
                click.echo(f"  备份目录：{config.backup_source_dir}", err=True)
                sys.exit(1)
            
            root_dir = actual_dir
        
        # Adjust output directory based on actual source directory if using default out_dir
        adjusted_out_dir = out_dir
        if out_dir == "../导出素材" and root_dir:  # Using default out_dir and have resolved source directory
            # Always adjust export base directory based on actual source directory used
            export_base = config.get_export_base_dir()
            adjusted_out_dir = os.path.join(export_base, "导出素材")
        
        # 应用传入的视频处理参数
        config.count = count
        config.min_duration = min_sec
        config.max_duration = max_sec
        config.date_str = date
        config.random_start = random_start
        config.seed = seed
        config.use_hardware = not sw
        config.target_fps = fps
        config.smart_fps = smart_fps
        config.canvas = canvas
        config.font_file = font_file
        config.footer_text = footer_text
        config.side_text = side_text
        
        # Handle tail file similar to process command
        if tail_file:
            # Explicit tail file
            if os.path.isfile(tail_file):
                config.tail_file = tail_file
            else:
                click.echo(f"⚠️ 指定的尾部文件不存在：{tail_file}")
                config.tail_file = None
        else:
            # Check for tail.mp4 in assets directory (new structure)
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            default_tail = os.path.join(project_root, "assets", "tail.mp4")
            if os.path.isfile(default_tail):
                config.tail_file = default_tail
            elif config.tail_file:
                # Check if the config file tail_file path exists relative to project root
                config_tail_path = os.path.join(project_root, config.tail_file) if not os.path.isabs(config.tail_file) else config.tail_file
                if not os.path.isfile(config_tail_path):
                    click.echo(f"⚠️ 配置中的尾部文件不存在：{config_tail_path}")
                    config.tail_file = None
        
        config.jobs = jobs
        config.temp_dir = temp_dir
        config.keep_temp = keep_temp
        config.output_dir = adjusted_out_dir
        config.tail_cache_dir = tail_cache_dir
        config.refresh_tail_cache = refresh_tail_cache
        config.fast_mode = fast_mode
        config.filter_threads = filter_threads
        config.verbose = verbose
        
        # 创建状态更新回调函数（自动更新开启）
        def status_update_callback(drama_name: str, new_status: str):
            """更新飞书表格中剧目的状态"""
            if drama_name in drama_records:
                record_id = drama_records[drama_name]
                try:
                    success = client.update_record_status(record_id, new_status)
                    if success:
                        click.echo(f"✅ 已更新 '{drama_name}' 状态为 '{new_status}'")
                    else:
                        click.echo(f"⚠️ 更新 '{drama_name}' 状态失败，但不影响处理流程", err=True)
                except Exception as e:
                    click.echo(f"⚠️ 更新 '{drama_name}' 状态时出错: {e}，但不影响处理流程", err=True)
        
        # 初始化处理器（自动开启状态更新回调）
        processor = DramaProcessor(config, status_callback=status_update_callback)
        
        # 开始处理
        click.echo(f"\n🎬 开始自动剪辑从飞书获取的剧目...")
        total_done, total_planned = processor.process_all_dramas(str(root_dir))
        
        click.echo(f"\n🎯 自动剪辑完成：{total_done}/{total_planned} 条素材生成成功")
        
        if total_done < total_planned:
            sys.exit(1)  # Partial failure
    
    except Exception as e:
        click.echo(f"❌ 自动剪辑失败: {e}", err=True)
        if ctx.obj.get("debug"):
            import traceback
            traceback.print_exc()
        sys.exit(1)


@feishu_command.command("select")
@click.option("--status", type=str, default="待剪辑", help="筛选状态（默认：待剪辑）")
@click.argument("root_dir", type=click.Path(exists=True, file_okay=False, path_type=Path), required=False)
# Material generation settings
@click.option("--count", type=int, default=10, help="每部短剧生成素材条数量（默认10）")
@click.option("--min-sec", type=float, default=480, help="每条素材最小时长（默认480s=8分钟）")
@click.option("--max-sec", type=float, default=900, help="每条素材最大时长（默认900s=15分钟）")
@click.option("--date", type=str, default=None, help="文件名前缀日期，如 8.26；默认当天")
# Random start settings
@click.option("--random-start/--no-random-start", default=True, help="随机起点，提升多样性（默认开启）")
@click.option("--seed", type=int, default=None, help="随机起点种子；不传则每次运行都会不同")
# Video settings
@click.option("--sw", is_flag=True, help="使用软编(libx264)；默认硬编(h264_videotoolbox)")
@click.option("--fps", type=int, default=60, help="输出帧率（默认60）")
@click.option("--smart-fps/--no-smart-fps", default=True, help="自适应帧率：源<40fps 用源帧率，否则封顶45fps（默认开启）")
@click.option("--canvas", type=str, default=None, help="参考画布：'WxH' 或 'first'；默认自动选择最常见分辨率")
# Text settings
@click.option("--font-file", type=str, default=None, help="中文字体文件路径")
@click.option("--footer-text", type=str, default="热门短剧 休闲必看", help="底部居中文案")
@click.option("--side-text", type=str, default="剧情纯属虚构 请勿模仿", help="右上竖排文案（可横排传入，脚本会自动竖排化）")
# Tail settings
@click.option("--tail-file", type=str, default=None, help="尾部引导视频路径（默认脚本同级 tail.mp4；不存在则跳过）")
# Performance settings
@click.option("--jobs", type=int, default=1, help="每部剧内的并发生成数（默认1；建议2~4）")
# Directory settings
@click.option("--temp-dir", type=str, default=None, help="临时工作目录根（默认 /tmp）")
@click.option("--keep-temp", is_flag=True, help="保留临时目录，便于调试（默认不保留）")
@click.option("--out-dir", type=str, default="../导出素材", help="自定义导出目录（默认 ../导出素材）")
# Tail cache settings
@click.option("--tail-cache-dir", type=str, default="/tmp/tails_cache", help="尾部规范化缓存目录（默认 /tmp/tails_cache）")
@click.option("--refresh-tail-cache", is_flag=True, help="强制刷新尾部缓存")
# Processing optimizations
@click.option("--fast-mode", is_flag=True, help="更快：关闭 eq/hue 随机色彩扰动，仅保留缩放/裁切/填充与文字")
@click.option("--filter-threads", type=int, default=max(2, (os.cpu_count() or 4)//2), help="滤镜并行线程数（默认=CPU核数一半，至少2）")
@click.option("--verbose", is_flag=True, help="详细日志：显示完整的FFmpeg命令和更多调试信息")
@click.pass_context  
def feishu_select(ctx, status: str, root_dir: Optional[Path],
    # Material generation
    count: int, min_sec: float, max_sec: float, date: Optional[str],
    # Random start
    random_start: bool, seed: Optional[int],
    # Video settings
    sw: bool, fps: int, smart_fps: bool, canvas: Optional[str],
    # Text settings
    font_file: Optional[str], footer_text: str, side_text: str,
    # Tail settings
    tail_file: Optional[str],
    # Performance
    jobs: int,
    # Directories
    temp_dir: Optional[str], keep_temp: bool, out_dir: str,
    # Tail cache
    tail_cache_dir: str, refresh_tail_cache: bool,
    # Optimizations
    fast_mode: bool, filter_threads: int, verbose: bool):
    """从飞书表格选择特定剧目进行剪辑，自动更新状态。"""
    config = ctx.obj.get("config") or ProcessingConfig()
    
    if not config.feishu:
        click.echo("❌ 飞书配置未设置，请在配置文件中添加飞书相关配置", err=True)
        sys.exit(1)
    
    try:
        from ..integrations.feishu_client import FeishuClient, _convert_date_format
        
        client = FeishuClient(config.feishu)
        
        # 转换日期格式（如果指定了date参数）
        feishu_date_filter = None
        if date:
            try:
                feishu_date_filter = _convert_date_format(date)
                click.echo(f"📅 日期过滤: {date} -> {feishu_date_filter}")
            except ValueError as e:
                click.echo(f"⚠️ 日期格式转换失败: {e}", err=True)
                click.echo("将忽略日期过滤条件，继续处理...")
        
        # 获取剧名和对应的记录ID
        drama_records = client.get_pending_dramas_with_records(status_filter=status, date_filter=feishu_date_filter)
        dramas = list(drama_records.keys())
        
        # 更新显示的过滤条件描述
        filter_desc = f"状态为 '{status}'"
        if feishu_date_filter:
            filter_desc += f" 且日期为 '{feishu_date_filter}'"
        
        if not dramas:
            click.echo(f"📋 未找到{filter_desc}的剧目")
            return
        
        click.echo("=" * 60)
        click.echo(f"📋 飞书表格中{filter_desc}的剧目")
        click.echo("=" * 60)
        
        for i, drama in enumerate(dramas, 1):
            click.echo(f"{i:2d}. {drama}")
        
        click.echo("=" * 60)
        
        # 用户选择剧目
        while True:
            try:
                choice = click.prompt("\n请选择要剪辑的剧目编号（多个编号用逗号分隔，如: 1,3,5）", type=str)
                
                # 解析用户输入
                selected_indices = []
                for part in choice.split(','):
                    part = part.strip()
                    if '-' in part:
                        # 支持范围选择，如 1-3
                        start, end = map(int, part.split('-'))
                        selected_indices.extend(range(start, end + 1))
                    else:
                        selected_indices.append(int(part))
                
                # 验证选择
                valid_indices = []
                selected_dramas = []
                for idx in selected_indices:
                    if 1 <= idx <= len(dramas):
                        if idx not in valid_indices:  # 去重
                            valid_indices.append(idx)
                            selected_dramas.append(dramas[idx - 1])
                    else:
                        click.echo(f"⚠️ 编号 {idx} 超出范围，已忽略")
                
                if not selected_dramas:
                    click.echo("❌ 没有选择有效的剧目，请重新选择")
                    continue
                
                break
                
            except ValueError:
                click.echo("❌ 输入格式错误，请输入数字编号")
            except KeyboardInterrupt:
                click.echo("\n取消选择")
                return
        
        # 显示选择的剧目
        click.echo(f"\n📌 已选择 {len(selected_dramas)} 部剧目：")
        for i, drama in enumerate(selected_dramas, 1):
            click.echo(f"  {i}. {drama}")
        
        # 确认处理
        if not click.confirm(f"\n确认要剪辑这 {len(selected_dramas)} 部剧吗？（状态将自动更新）"):
            click.echo("取消处理")
            return
        
        # 更新配置以包含传入的参数
        config.include = selected_dramas
        config.full = False
        config.no_interactive = True  # 禁用交互式选择
        
        # Handle default source directory
        if root_dir is None:
            actual_dir = Path(config.get_actual_source_dir())
            
            if not actual_dir.exists():
                click.echo(f"错误：主目录和备份目录都不存在：", err=True)
                click.echo(f"  主目录：{config.default_source_dir}", err=True)
                click.echo(f"  备份目录：{config.backup_source_dir}", err=True)
                sys.exit(1)
            
            root_dir = actual_dir
        
        # Adjust output directory based on actual source directory if using default out_dir
        adjusted_out_dir = out_dir
        if out_dir == "../导出素材" and root_dir:  # Using default out_dir and have resolved source directory
            # Always adjust export base directory based on actual source directory used
            export_base = config.get_export_base_dir()
            adjusted_out_dir = os.path.join(export_base, "导出素材")
        
        # 应用传入的视频处理参数
        config.count = count
        config.min_duration = min_sec
        config.max_duration = max_sec
        config.date_str = date
        config.random_start = random_start
        config.seed = seed
        config.use_hardware = not sw
        config.target_fps = fps
        config.smart_fps = smart_fps
        config.canvas = canvas
        config.font_file = font_file
        config.footer_text = footer_text
        config.side_text = side_text
        
        # Handle tail file similar to process command
        if tail_file:
            # Explicit tail file
            if os.path.isfile(tail_file):
                config.tail_file = tail_file
            else:
                click.echo(f"⚠️ 指定的尾部文件不存在：{tail_file}")
                config.tail_file = None
        else:
            # Check for tail.mp4 in assets directory (new structure)
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            default_tail = os.path.join(project_root, "assets", "tail.mp4")
            if os.path.isfile(default_tail):
                config.tail_file = default_tail
            elif config.tail_file:
                # Check if the config file tail_file path exists relative to project root
                config_tail_path = os.path.join(project_root, config.tail_file) if not os.path.isabs(config.tail_file) else config.tail_file
                if not os.path.isfile(config_tail_path):
                    click.echo(f"⚠️ 配置中的尾部文件不存在：{config_tail_path}")
                    config.tail_file = None
        
        config.jobs = jobs
        config.temp_dir = temp_dir
        config.keep_temp = keep_temp
        config.output_dir = adjusted_out_dir
        config.tail_cache_dir = tail_cache_dir
        config.refresh_tail_cache = refresh_tail_cache
        config.fast_mode = fast_mode
        config.filter_threads = filter_threads
        config.verbose = verbose
        
        # 创建状态更新回调函数（自动更新开启）
        def status_update_callback(drama_name: str, new_status: str):
            """更新飞书表格中剧目的状态"""
            if drama_name in drama_records:
                record_id = drama_records[drama_name]
                try:
                    success = client.update_record_status(record_id, new_status)
                    if success:
                        click.echo(f"✅ 已更新 '{drama_name}' 状态为 '{new_status}'")
                    else:
                        click.echo(f"⚠️ 更新 '{drama_name}' 状态失败，但不影响处理流程", err=True)
                except Exception as e:
                    click.echo(f"⚠️ 更新 '{drama_name}' 状态时出错: {e}，但不影响处理流程", err=True)
        
        # 初始化处理器（自动开启状态更新回调）
        processor = DramaProcessor(config, status_callback=status_update_callback)
        
        # 开始处理
        click.echo(f"\n🎬 开始剪辑选择的剧目...")
        total_done, total_planned = processor.process_all_dramas(str(root_dir))
        
        click.echo(f"\n🎯 选择性剪辑完成：{total_done}/{total_planned} 条素材生成成功")
        
        if total_done < total_planned:
            sys.exit(1)  # Partial failure
    
    except Exception as e:
        click.echo(f"❌ 选择性剪辑失败: {e}", err=True)
        if ctx.obj.get("debug"):
            import traceback
            traceback.print_exc()
        sys.exit(1)


@feishu_command.command("sync")
@click.option("--status", type=str, default="待剪辑", help="筛选状态（默认：待剪辑）")
@click.option("--dry-run", is_flag=True, help="预览模式，不实际处理")
@click.option("--auto-update", is_flag=True, help="自动更新剧目状态：开始处理时更新为'剪辑中'，完成后更新为'待上传'")
@click.argument("root_dir", type=click.Path(exists=True, file_okay=False, path_type=Path), required=False)
# Material generation settings
@click.option("--count", type=int, default=10, help="每部短剧生成素材条数量（默认10）")
@click.option("--min-sec", type=float, default=480, help="每条素材最小时长（默认480s=8分钟）")
@click.option("--max-sec", type=float, default=900, help="每条素材最大时长（默认900s=15分钟）")
@click.option("--date", type=str, default=None, help="文件名前缀日期，如 8.26；默认当天")
# Random start settings
@click.option("--random-start/--no-random-start", default=True, help="随机起点，提升多样性（默认开启）")
@click.option("--seed", type=int, default=None, help="随机起点种子；不传则每次运行都会不同")
# Video settings
@click.option("--sw", is_flag=True, help="使用软编(libx264)；默认硬编(h264_videotoolbox)")
@click.option("--fps", type=int, default=60, help="输出帧率（默认60）")
@click.option("--smart-fps/--no-smart-fps", default=True, help="自适应帧率：源<40fps 用源帧率，否则封顶45fps（默认开启）")
@click.option("--canvas", type=str, default=None, help="参考画布：'WxH' 或 'first'；默认自动选择最常见分辨率")
# Text settings
@click.option("--font-file", type=str, default=None, help="中文字体文件路径")
@click.option("--footer-text", type=str, default="热门短剧 休闲必看", help="底部居中文案")
@click.option("--side-text", type=str, default="剧情纯属虚构 请勿模仿", help="右上竖排文案（可横排传入，脚本会自动竖排化）")
# Tail settings
@click.option("--tail-file", type=str, default=None, help="尾部引导视频路径（默认脚本同级 tail.mp4；不存在则跳过）")
# Performance settings
@click.option("--jobs", type=int, default=1, help="每部剧内的并发生成数（默认1；建议2~4）")
# Directory settings
@click.option("--temp-dir", type=str, default=None, help="临时工作目录根（默认 /tmp）")
@click.option("--keep-temp", is_flag=True, help="保留临时目录，便于调试（默认不保留）")
@click.option("--out-dir", type=str, default="../导出素材", help="自定义导出目录（默认 ../导出素材）")
# Tail cache settings
@click.option("--tail-cache-dir", type=str, default="/tmp/tails_cache", help="尾部规范化缓存目录（默认 /tmp/tails_cache）")
@click.option("--refresh-tail-cache", is_flag=True, help="强制刷新尾部缓存")
# Processing optimizations
@click.option("--fast-mode", is_flag=True, help="更快：关闭 eq/hue 随机色彩扰动，仅保留缩放/裁切/填充与文字")
@click.option("--filter-threads", type=int, default=max(2, (os.cpu_count() or 4)//2), help="滤镜并行线程数（默认=CPU核数一半，至少2）")
@click.option("--verbose", is_flag=True, help="详细日志：显示完整的FFmpeg命令和更多调试信息")
@click.pass_context  
def feishu_sync(ctx, status: str, dry_run: bool, auto_update: bool, root_dir: Optional[Path],
    # Material generation
    count: int, min_sec: float, max_sec: float, date: Optional[str],
    # Random start
    random_start: bool, seed: Optional[int],
    # Video settings
    sw: bool, fps: int, smart_fps: bool, canvas: Optional[str],
    # Text settings
    font_file: Optional[str], footer_text: str, side_text: str,
    # Tail settings
    tail_file: Optional[str],
    # Performance
    jobs: int,
    # Directories
    temp_dir: Optional[str], keep_temp: bool, out_dir: str,
    # Tail cache
    tail_cache_dir: str, refresh_tail_cache: bool,
    # Optimizations
    fast_mode: bool, filter_threads: int, verbose: bool):
    """从飞书表格获取待处理剧目列表并自动处理。"""
    config = ctx.obj.get("config") or ProcessingConfig()
    
    if not config.feishu:
        click.echo("❌ 飞书配置未设置，请在配置文件中添加飞书相关配置", err=True)
        sys.exit(1)
    
    try:
        from ..integrations.feishu_client import FeishuClient, _convert_date_format
        
        client = FeishuClient(config.feishu)
        
        # 转换日期格式（如果指定了date参数）
        feishu_date_filter = None
        if date:
            try:
                feishu_date_filter = _convert_date_format(date)
                click.echo(f"📅 日期过滤: {date} -> {feishu_date_filter}")
            except ValueError as e:
                click.echo(f"⚠️ 日期格式转换失败: {e}", err=True)
                click.echo("将忽略日期过滤条件，继续处理...")
        
        if auto_update:
            # 获取剧名和对应的记录ID
            drama_records = client.get_pending_dramas_with_records(status_filter=status, date_filter=feishu_date_filter)
            dramas = list(drama_records.keys())
        else:
            # 只获取剧名列表
            dramas = client.get_pending_dramas(status_filter=status, date_filter=feishu_date_filter)
            drama_records = {}
        
        # 更新显示的过滤条件描述
        filter_desc = f"状态为 '{status}'"
        if feishu_date_filter:
            filter_desc += f" 且日期为 '{feishu_date_filter}'"
        
        if not dramas:
            click.echo(f"📋 未找到{filter_desc}的剧目")
            return
        
        click.echo("=" * 60)
        click.echo(f"📋 从飞书获取到 {len(dramas)} 部待处理剧目")
        click.echo("=" * 60)
        
        for i, drama in enumerate(dramas, 1):
            click.echo(f"{i:2d}. {drama}")
        
        if dry_run:
            click.echo(f"\n🔍 预览模式：将处理上述 {len(dramas)} 部剧")
            return
        
        # 确认处理
        if not click.confirm(f"\n确认要处理这 {len(dramas)} 部剧吗？"):
            click.echo("取消处理")
            return
        
        # 更新配置以包含传入的参数
        config.include = dramas
        config.full = False
        config.no_interactive = True  # 禁用交互式选择
        
        # Handle default source directory
        if root_dir is None:
            actual_dir = Path(config.get_actual_source_dir())
            
            if not actual_dir.exists():
                click.echo(f"错误：主目录和备份目录都不存在：", err=True)
                click.echo(f"  主目录：{config.default_source_dir}", err=True)
                click.echo(f"  备份目录：{config.backup_source_dir}", err=True)
                sys.exit(1)
            
            root_dir = actual_dir
        
        # Adjust output directory based on actual source directory if using default out_dir
        adjusted_out_dir = out_dir
        if out_dir == "../导出素材" and root_dir:  # Using default out_dir and have resolved source directory
            # Always adjust export base directory based on actual source directory used
            export_base = config.get_export_base_dir()
            adjusted_out_dir = os.path.join(export_base, "导出素材")
        
        # 应用传入的视频处理参数
        config.count = count
        config.min_duration = min_sec
        config.max_duration = max_sec
        config.date_str = date
        config.random_start = random_start
        config.seed = seed
        config.use_hardware = not sw
        config.target_fps = fps
        config.smart_fps = smart_fps
        config.canvas = canvas
        config.font_file = font_file
        config.footer_text = footer_text
        config.side_text = side_text
        
        # Handle tail file similar to process command
        if tail_file:
            # Explicit tail file
            if os.path.isfile(tail_file):
                config.tail_file = tail_file
            else:
                click.echo(f"⚠️ 指定的尾部文件不存在：{tail_file}")
                config.tail_file = None
        else:
            # Check for tail.mp4 in assets directory (new structure)
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            default_tail = os.path.join(project_root, "assets", "tail.mp4")
            if os.path.isfile(default_tail):
                config.tail_file = default_tail
            elif config.tail_file:
                # Check if the config file tail_file path exists relative to project root
                config_tail_path = os.path.join(project_root, config.tail_file) if not os.path.isabs(config.tail_file) else config.tail_file
                if not os.path.isfile(config_tail_path):
                    click.echo(f"⚠️ 配置中的尾部文件不存在：{config_tail_path}")
                    config.tail_file = None
        
        config.jobs = jobs
        config.temp_dir = temp_dir
        config.keep_temp = keep_temp
        config.output_dir = adjusted_out_dir
        config.tail_cache_dir = tail_cache_dir
        config.refresh_tail_cache = refresh_tail_cache
        config.fast_mode = fast_mode
        config.filter_threads = filter_threads
        config.verbose = verbose
        
        # 创建状态更新回调函数
        def status_update_callback(drama_name: str, new_status: str):
            """更新飞书表格中剧目的状态"""
            if auto_update and drama_name in drama_records:
                record_id = drama_records[drama_name]
                try:
                    success = client.update_record_status(record_id, new_status)
                    if success:
                        click.echo(f"✅ 已更新 '{drama_name}' 状态为 '{new_status}'")
                    else:
                        click.echo(f"⚠️ 更新 '{drama_name}' 状态失败，但不影响处理流程", err=True)
                except Exception as e:
                    click.echo(f"⚠️ 更新 '{drama_name}' 状态时出错: {e}，但不影响处理流程", err=True)
        
        # 初始化处理器（如果启用自动更新，传入回调函数）
        callback = status_update_callback if auto_update else None
        processor = DramaProcessor(config, status_callback=callback)
        
        # 开始处理
        click.echo(f"\n🎬 开始处理从飞书获取的剧目...")
        total_done, total_planned = processor.process_all_dramas(str(root_dir))
        
        click.echo(f"\n🎯 飞书同步处理完成：{total_done}/{total_planned} 条素材生成成功")
        
        if total_done < total_planned:
            sys.exit(1)  # Partial failure
    
    except Exception as e:
        click.echo(f"❌ 飞书同步处理失败: {e}", err=True)
        if ctx.obj.get("debug"):
            import traceback
            traceback.print_exc()
        sys.exit(1)