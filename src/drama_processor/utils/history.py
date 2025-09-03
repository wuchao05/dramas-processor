"""剪辑历史记录管理器"""

import json
import shutil
from datetime import datetime, date
from pathlib import Path
from typing import List, Optional, Dict, Any
from collections import defaultdict

from ..models.history import (
    ProcessingSession, DramaRecord, MaterialRecord,
    DailySummary, MonthlySummary, AllTimeSummary
)
from ..models.config import ProcessingConfig


class HistoryManager:
    """剪辑历史记录管理器"""
    
    def __init__(self, base_dir: Optional[Path] = None):
        """
        初始化历史记录管理器
        
        Args:
            base_dir: 历史记录存储根目录，默认为项目根目录下的 history/
        """
        if base_dir is None:
            # 查找项目根目录（包含 pyproject.toml 的目录）
            current = Path.cwd()
            while current != current.parent:
                if (current / "pyproject.toml").exists():
                    base_dir = current / "history"
                    break
                current = current.parent
            else:
                # 如果找不到项目根目录，使用当前目录
                base_dir = Path.cwd() / "history"
        
        self.base_dir = Path(base_dir)
        self._ensure_directories()
    
    def _ensure_directories(self):
        """确保所需目录存在"""
        (self.base_dir / "sessions").mkdir(parents=True, exist_ok=True)
        (self.base_dir / "summary" / "daily").mkdir(parents=True, exist_ok=True)
        (self.base_dir / "summary" / "monthly").mkdir(parents=True, exist_ok=True)
        (self.base_dir / "exports" / "by-drama").mkdir(parents=True, exist_ok=True)
        (self.base_dir / "exports" / "by-date").mkdir(parents=True, exist_ok=True)
    
    def create_session(self, config: ProcessingConfig, command_line: str) -> ProcessingSession:
        """创建新的处理会话"""
        session_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        
        session = ProcessingSession(
            session_id=session_id,
            start_time=datetime.now(),
            command_line=command_line,
            source_directory=config.default_source_dir,
            output_directory=config.output_dir,
            total_dramas=0,
            successful_dramas=0,
            total_materials=0,
            total_processing_time=0.0,
            total_size_mb=0.0
        )
        
        return session
    
    def add_drama_record(self, session: ProcessingSession, drama_info: Dict[str, Any], 
                        config: ProcessingConfig, processing_time: float) -> DramaRecord:
        """添加短剧处理记录"""
        
        # 创建素材记录
        materials = []
        for material_path in drama_info.get('materials', []):
            if Path(material_path).exists():
                stat = Path(material_path).stat()
                size_mb = stat.st_size / (1024 * 1024)
                
                # 从文件名推断时长信息（简化版，实际可以用ffprobe获取）
                material = MaterialRecord(
                    filename=Path(material_path).name,
                    duration=drama_info.get('duration_per_material', 600),  # 默认10分钟
                    size_mb=size_mb,
                    start_time=0.0,  # 简化处理
                    end_time=drama_info.get('duration_per_material', 600),
                    created_at=datetime.now()
                )
                materials.append(material)
        
        # 处理时间信息
        start_time = datetime.now()
        end_time = datetime.now()
        
        # 如果提供了时间戳，使用它们
        if 'start_time' in drama_info:
            start_time = datetime.fromtimestamp(drama_info['start_time'])
        if 'end_time' in drama_info:
            end_time = datetime.fromtimestamp(drama_info['end_time'])
        
        # 创建短剧记录
        drama_record = DramaRecord(
            name=drama_info['name'],
            source_path=drama_info.get('source_path', ''),
            output_dir=drama_info['output_dir'],
            date_str=drama_info['date'],
            run_suffix=drama_info.get('run_suffix'),
            planned_count=drama_info['planned'],
            completed_count=drama_info['completed'],
            success_rate=drama_info['completed'] / drama_info['planned'] if drama_info['planned'] > 0 else 0.0,
            materials=materials,
            total_duration=drama_info.get('total_duration', 0.0),
            processing_time=processing_time,  # 总处理时间（秒）
            start_time=start_time,  # 开始时间
            end_time=end_time,  # 结束时间
            config_snapshot=config.model_dump()
        )
        
        # 添加到会话
        session.dramas.append(drama_record)
        session.total_dramas += 1
        if drama_record.is_completed:
            session.successful_dramas += 1
        session.total_materials += len(materials)
        session.total_processing_time += processing_time
        session.total_size_mb += drama_record.total_materials_size_mb
        
        return drama_record
    
    def finish_session(self, session: ProcessingSession):
        """完成会话并保存"""
        session.end_time = datetime.now()
        
        # 保存会话记录
        session_file = self.base_dir / "sessions" / f"{session.session_id}.json"
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(session.model_dump(mode='json'), f, ensure_ascii=False, indent=2)
        
        # 更新汇总统计
        self._update_summaries(session)
        
        # 更新导出索引
        self._update_export_indexes(session)
    
    def _update_summaries(self, session: ProcessingSession):
        """更新汇总统计"""
        session_date = session.start_time.date()
        date_str = session_date.strftime("%Y-%m-%d")
        month_str = session_date.strftime("%Y-%m")
        
        # 更新日度汇总
        daily_file = self.base_dir / "summary" / "daily" / f"{date_str}.json"
        daily_summary = self._load_or_create_daily_summary(daily_file, date_str)
        
        daily_summary.sessions.append(session.session_id)
        daily_summary.total_dramas += session.total_dramas
        daily_summary.successful_dramas += session.successful_dramas
        daily_summary.total_materials += session.total_materials
        daily_summary.total_size_mb += session.total_size_mb
        daily_summary.total_processing_time += session.total_processing_time
        
        # 更新当日处理的短剧列表
        for drama in session.dramas:
            if drama.name not in daily_summary.unique_dramas:
                daily_summary.unique_dramas.append(drama.name)
        
        with open(daily_file, 'w', encoding='utf-8') as f:
            json.dump(daily_summary.model_dump(mode='json'), f, ensure_ascii=False, indent=2)
        
        # 更新月度汇总
        monthly_file = self.base_dir / "summary" / "monthly" / f"{month_str}.json"
        monthly_summary = self._load_or_create_monthly_summary(monthly_file, month_str)
        
        if date_str not in monthly_summary.daily_summaries:
            monthly_summary.daily_summaries.append(date_str)
            monthly_summary.active_days += 1
        
        # 重新计算月度统计（从所有日度汇总中计算）
        self._recalculate_monthly_summary(monthly_summary, month_str)
        
        with open(monthly_file, 'w', encoding='utf-8') as f:
            json.dump(monthly_summary.model_dump(mode='json'), f, ensure_ascii=False, indent=2)
        
        # 更新全时段汇总
        self._update_all_time_summary(session)
    
    def _load_or_create_daily_summary(self, file_path: Path, date_str: str) -> DailySummary:
        """加载或创建日度汇总"""
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return DailySummary(**data)
        else:
            return DailySummary(
                date=date_str,
                total_dramas=0,
                successful_dramas=0,
                total_materials=0,
                total_size_mb=0.0,
                total_processing_time=0.0
            )
    
    def _load_or_create_monthly_summary(self, file_path: Path, month_str: str) -> MonthlySummary:
        """加载或创建月度汇总"""
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return MonthlySummary(**data)
        else:
            return MonthlySummary(
                year_month=month_str,
                total_dramas=0,
                successful_dramas=0,
                total_materials=0,
                total_size_mb=0.0,
                total_processing_time=0.0,
                active_days=0
            )
    
    def _recalculate_monthly_summary(self, monthly_summary: MonthlySummary, month_str: str):
        """重新计算月度汇总"""
        year, month = month_str.split('-')
        daily_dir = self.base_dir / "summary" / "daily"
        
        # 重置统计
        monthly_summary.total_dramas = 0
        monthly_summary.successful_dramas = 0
        monthly_summary.total_materials = 0
        monthly_summary.total_size_mb = 0.0
        monthly_summary.total_processing_time = 0.0
        monthly_summary.unique_dramas = []
        
        # 汇总当月所有日度数据
        for daily_file in daily_dir.glob(f"{year}-{month}-*.json"):
            with open(daily_file, 'r', encoding='utf-8') as f:
                daily_data = DailySummary(**json.load(f))
                
                monthly_summary.total_dramas += daily_data.total_dramas
                monthly_summary.successful_dramas += daily_data.successful_dramas
                monthly_summary.total_materials += daily_data.total_materials
                monthly_summary.total_size_mb += daily_data.total_size_mb
                monthly_summary.total_processing_time += daily_data.total_processing_time
                
                # 合并短剧列表
                for drama in daily_data.unique_dramas:
                    if drama not in monthly_summary.unique_dramas:
                        monthly_summary.unique_dramas.append(drama)
    
    def _update_all_time_summary(self, session: ProcessingSession):
        """更新全时段汇总"""
        all_time_file = self.base_dir / "summary" / "all-time.json"
        
        if all_time_file.exists():
            with open(all_time_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 处理datetime字段
                if data.get('first_session'):
                    data['first_session'] = datetime.fromisoformat(data['first_session'])
                if data.get('last_session'):
                    data['last_session'] = datetime.fromisoformat(data['last_session'])
                summary = AllTimeSummary(**data)
        else:
            summary = AllTimeSummary(
                total_sessions=0,
                total_dramas=0,
                successful_dramas=0,
                total_materials=0,
                total_size_mb=0.0,
                total_processing_time=0.0,
                active_days=0
            )
        
        # 更新统计
        summary.total_sessions += 1
        summary.total_dramas += session.total_dramas
        summary.successful_dramas += session.successful_dramas
        summary.total_materials += session.total_materials
        summary.total_size_mb += session.total_size_mb
        summary.total_processing_time += session.total_processing_time
        summary.last_session = session.start_time
        
        if summary.first_session is None:
            summary.first_session = session.start_time
        
        # 更新短剧列表
        for drama in session.dramas:
            if drama.name not in summary.unique_dramas:
                summary.unique_dramas.append(drama.name)
        
        # 计算活跃天数
        summary.active_days = len(list((self.base_dir / "summary" / "daily").glob("*.json")))
        
        with open(all_time_file, 'w', encoding='utf-8') as f:
            json.dump(summary.model_dump(mode='json'), f, ensure_ascii=False, indent=2)
    
    def _update_export_indexes(self, session: ProcessingSession):
        """更新导出索引"""
        session_date = session.start_time.strftime("%Y-%m-%d")
        
        # 按日期索引
        date_index_file = self.base_dir / "exports" / "by-date" / f"{session_date}.json"
        date_index = self._load_date_index(date_index_file)
        
        for drama in session.dramas:
            drama_info = {
                'session_id': session.session_id,
                'drama_name': drama.name,
                'output_dir': drama.output_dir,
                'materials_count': len(drama.materials),
                'completed': drama.is_completed,
                'size_mb': drama.total_materials_size_mb
            }
            date_index.append(drama_info)
        
        with open(date_index_file, 'w', encoding='utf-8') as f:
            json.dump(date_index, f, ensure_ascii=False, indent=2)
        
        # 按剧名索引
        for drama in session.dramas:
            drama_index_file = self.base_dir / "exports" / "by-drama" / f"{drama.name}.json"
            drama_index = self._load_drama_index(drama_index_file)
            
            record = {
                'session_id': session.session_id,
                'date': session_date,
                'output_dir': drama.output_dir,
                'materials': [m.filename for m in drama.materials],
                'materials_count': len(drama.materials),
                'completed': drama.is_completed,
                'size_mb': drama.total_materials_size_mb,
                'processing_time': drama.processing_time
            }
            drama_index.append(record)
            
            with open(drama_index_file, 'w', encoding='utf-8') as f:
                json.dump(drama_index, f, ensure_ascii=False, indent=2)
    
    def _load_date_index(self, file_path: Path) -> List[Dict[str, Any]]:
        """加载日期索引"""
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    
    def _load_drama_index(self, file_path: Path) -> List[Dict[str, Any]]:
        """加载剧名索引"""
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    
    def get_recent_sessions(self, limit: int = 10) -> List[ProcessingSession]:
        """获取最近的处理会话"""
        sessions_dir = self.base_dir / "sessions"
        session_files = sorted(sessions_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        
        sessions = []
        for session_file in session_files[:limit]:
            with open(session_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 处理datetime字段
                data['start_time'] = datetime.fromisoformat(data['start_time'])
                if data.get('end_time'):
                    data['end_time'] = datetime.fromisoformat(data['end_time'])
                
                # 处理嵌套的datetime字段
                for drama in data.get('dramas', []):
                    drama['start_time'] = datetime.fromisoformat(drama['start_time'])
                    drama['end_time'] = datetime.fromisoformat(drama['end_time'])
                    for material in drama.get('materials', []):
                        material['created_at'] = datetime.fromisoformat(material['created_at'])
                
                sessions.append(ProcessingSession(**data))
        
        return sessions
    
    def get_drama_history(self, drama_name: str) -> List[Dict[str, Any]]:
        """获取特定短剧的处理历史"""
        drama_index_file = self.base_dir / "exports" / "by-drama" / f"{drama_name}.json"
        return self._load_drama_index(drama_index_file)
    
    def get_all_time_stats(self) -> Optional[AllTimeSummary]:
        """获取全时段统计"""
        all_time_file = self.base_dir / "summary" / "all-time.json"
        if all_time_file.exists():
            with open(all_time_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data.get('first_session'):
                    data['first_session'] = datetime.fromisoformat(data['first_session'])
                if data.get('last_session'):
                    data['last_session'] = datetime.fromisoformat(data['last_session'])
                return AllTimeSummary(**data)
        return None
