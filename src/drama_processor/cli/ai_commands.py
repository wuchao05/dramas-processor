"""AI功能相关的CLI命令"""

import click
import logging
from pathlib import Path
import json
import sys
from typing import Optional

from ..models.config import ProcessingConfig
from ..ai import SceneAnalyzer
from ..ai.ai_enhanced_processor import create_ai_enhanced_processor

logger = logging.getLogger(__name__)


@click.group()
def ai():
    """AI功能相关命令"""
    pass


@ai.command()
@click.argument("video_path", type=click.Path(exists=True, path_type=Path))
@click.option("--output", "-o", type=click.Path(path_type=Path), 
              help="输出结果文件路径（JSON格式）")
@click.option("--sample-rate", type=float, default=1.0,
              help="采样率（每秒帧数，默认1.0）")
def analyze_scenes(video_path: Path, output: Optional[Path], sample_rate: float):
    """分析视频场景和剪辑点"""
    
    click.echo(f"🎬 开始分析视频场景: {video_path}")
    
    try:
        # 初始化场景分析器
        analyzer = SceneAnalyzer()
        
        # 分析场景
        scenes = analyzer.analyze_video_scenes(video_path, sample_rate)
        
        # 简化处理：所有场景都认为是有效的
        high_quality_scenes = scenes
        
        # 寻找最佳剪辑点
        optimal_points = analyzer.find_optimal_cut_points(
            video_path, target_duration=600, min_duration=300, max_duration=900
        )
        
        # 准备结果
        result = {
            "video_path": str(video_path),
            "total_scenes": len(scenes),
            "high_quality_scenes": len(high_quality_scenes),
            "scenes": [
                {
                    "start_time": scene.start_time,
                    "end_time": scene.end_time,
                    "duration": scene.end_time - scene.start_time,
                    "quality_score": scene.quality_score,
                    "scene_type": scene.scene_type
                }
                for scene in scenes
            ],
            "optimal_cut_points": [
                {
                    "timestamp": point.timestamp,
                    "confidence": point.confidence,
                    "cut_type": point.cut_type
                }
                for point in optimal_points
            ]
        }
        
        # 输出结果
        if output:
            with open(output, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            click.echo(f"✅ 分析结果已保存到: {output}")
        else:
            click.echo("\n📊 场景分析结果:")
            click.echo(f"   总场景数: {len(scenes)}")
            click.echo(f"   检测到的场景数: {len(high_quality_scenes)}")
            click.echo(f"   推荐剪辑点数: {len(optimal_points)}")
            
            if optimal_points:
                click.echo("\n🎯 推荐剪辑点:")
                for i, point in enumerate(optimal_points[:5], 1):
                    click.echo(f"   {i}. {point.timestamp:.1f}s - {point.cut_type} (置信度: {point.confidence:.2f})")
    
    except Exception as e:
        click.echo(f"❌ 场景分析失败: {e}", err=True)
        sys.exit(1)


# 合规检测功能已移除


@ai.command()
@click.argument("video_path", type=click.Path(exists=True, path_type=Path))
@click.option("--output-dir", type=click.Path(path_type=Path),
              help="输出目录（默认为视频文件同级目录）")
@click.option("--target-duration", type=float, default=600.0,
              help="目标剪辑时长（秒，默认600秒即10分钟）")
def analyze_video(video_path: Path, output_dir: Optional[Path], target_duration: float):
    """AI智能视频分析 - 场景检测与最佳剪辑点推荐"""
    
    if output_dir is None:
        output_dir = video_path.parent / f"{video_path.stem}_ai_analysis"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    click.echo(f"🔍 开始AI智能视频分析: {video_path}")
    
    try:
        # AI场景分析
        click.echo("🎬 执行AI场景检测...")
        analyzer = SceneAnalyzer()
        scenes = analyzer.analyze_video_scenes(video_path)
        
        click.echo("🎯 寻找最佳剪辑点...")
        optimal_cuts = analyzer.find_optimal_cut_points(
            video_path, 
            target_duration=target_duration,
            min_duration=target_duration * 0.5,
            max_duration=target_duration * 1.5
        )
        
        # 场景分析结果
        scene_results = {
            "total_scenes": len(scenes),
            "high_quality_scenes": len([s for s in scenes if s.quality_score > 0.7]),
            "scenes": [
                {
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "duration": s.end_time - s.start_time,
                    "quality_score": s.quality_score,
                    "scene_type": s.scene_type
                }
                for s in scenes
            ]
        }
        
        # 最佳剪辑点结果
        cuts_results = {
            "target_duration": target_duration,
            "optimal_cuts_count": len(optimal_cuts),
            "cuts": [
                {
                    "timestamp": cut.timestamp,
                    "confidence": cut.confidence,
                    "cut_type": cut.cut_type
                }
                for cut in optimal_cuts
            ]
        }
        
        # 保存结果文件
        scene_output = output_dir / "scenes_analysis.json"
        with open(scene_output, 'w', encoding='utf-8') as f:
            json.dump(scene_results, f, ensure_ascii=False, indent=2)
        
        cuts_output = output_dir / "optimal_cuts.json"
        with open(cuts_output, 'w', encoding='utf-8') as f:
            json.dump(cuts_results, f, ensure_ascii=False, indent=2)
        
        # 综合分析摘要
        summary = {
            "video_path": str(video_path),
            "analysis_results": {
                "scenes_detected": len(scenes),
                "optimal_cuts_found": len(optimal_cuts),
                "target_duration": target_duration,
                "high_quality_scenes": len([s for s in scenes if s.quality_score > 0.7])
            },
            "output_files": {
                "scenes": str(scene_output),
                "optimal_cuts": str(cuts_output)
            }
        }
        
        summary_output = output_dir / "analysis_summary.json"
        with open(summary_output, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        # 控制台输出
        click.echo(f"\n✅ AI智能分析完成!")
        click.echo(f"   🎬 检测到 {len(scenes)} 个场景")
        click.echo(f"   🎯 找到 {len(optimal_cuts)} 个最佳剪辑点")
        
        if optimal_cuts:
            click.echo(f"   💡 推荐剪辑点（前3个）:")
            for i, cut in enumerate(optimal_cuts[:3], 1):
                click.echo(f"      {i}. {cut.timestamp:.1f}s ({cut.cut_type}, 置信度: {cut.confidence:.2f})")
        
        click.echo(f"\n📂 结果保存在: {output_dir}")
        click.echo(f"📄 分析摘要: {summary_output}")
        
    except Exception as e:
        click.echo(f"❌ AI智能分析失败: {e}", err=True)
        sys.exit(1)


@ai.command()
@click.option("--list-models", is_flag=True, help="列出可用模型")
@click.argument("model_name", required=False)
@click.option("--force", is_flag=True, help="强制重新下载")
def download_model(list_models: bool, model_name: Optional[str], force: bool):
    """下载AI模型"""
    
    try:
        from ..ai.models.model_downloader import ModelDownloader
        
        downloader = ModelDownloader()
        
        if list_models:
            click.echo("📋 可用模型:")
            for name, desc in downloader.list_available_models().items():
                status = "✅ 已下载" if downloader.get_model_path(name) else "⬇️  未下载"
                click.echo(f"   {name}: {desc} ({status})")
            return
        
        if not model_name:
            click.echo("❌ 请指定模型名称或使用 --list-models 查看可用模型", err=True)
            sys.exit(1)
        
        click.echo(f"📥 下载模型: {model_name}")
        model_path = downloader.download_model(model_name, force)
        click.echo(f"✅ 模型下载完成: {model_path}")
        
    except Exception as e:
        click.echo(f"❌ 模型下载失败: {e}", err=True)
        sys.exit(1)


@ai.command()
@click.argument("test_video", type=click.Path(exists=True, path_type=Path))
@click.option("--duration", type=int, default=60, help="测试时长（秒）")
def benchmark(test_video: Path, duration: int):
    """AI功能性能基准测试"""
    
    click.echo(f"⚡ 开始AI功能性能测试: {test_video}")
    click.echo(f"🕐 测试时长: {duration}秒")
    
    import time
    
    # 场景检测性能测试
    click.echo("\n🎬 测试场景检测性能...")
    try:
        start_time = time.time()
        analyzer = SceneAnalyzer()
        scenes = analyzer.analyze_video_scenes(test_video, sample_rate=0.5)  # 降低采样率
        scene_time = time.time() - start_time
        
        click.echo(f"   检测到 {len(scenes)} 个场景")
        click.echo(f"   耗时: {scene_time:.2f}秒")
        click.echo(f"   速度: {duration/scene_time:.1f}x 实时")
        
    except Exception as e:
        click.echo(f"   ❌ 场景检测测试失败: {e}")
    
    # 合规检查功能已移除
    
    click.echo(f"\n🏁 性能测试完成!")


# 添加到主CLI
def add_ai_commands(main_cli):
    """将AI命令添加到主CLI"""
    main_cli.add_command(ai)
