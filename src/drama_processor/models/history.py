"""剪辑历史记录数据模型"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path
from pydantic import BaseModel, Field


class MaterialRecord(BaseModel):
    """单个素材记录"""
    filename: str = Field(description="素材文件名")
    duration: float = Field(description="素材时长（秒）")
    size_mb: float = Field(description="文件大小（MB）")
    start_time: float = Field(description="剪辑起始时间")
    end_time: float = Field(description="剪辑结束时间")
    created_at: datetime = Field(description="创建时间")


class DramaRecord(BaseModel):
    """单部短剧处理记录"""
    name: str = Field(description="短剧名称")
    source_path: str = Field(description="源文件路径")
    output_dir: str = Field(description="输出目录")
    date_str: str = Field(description="日期标识")
    run_suffix: Optional[str] = Field(default=None, description="运行批次后缀")
    
    # 计划与实际
    planned_count: int = Field(description="计划生成数量")
    completed_count: int = Field(description="实际完成数量")
    success_rate: float = Field(description="成功率")
    
    # 素材详情
    materials: List[MaterialRecord] = Field(default_factory=list, description="生成的素材列表")
    
    # 处理信息
    total_duration: float = Field(description="源视频总时长")
    processing_time: float = Field(description="该剧总处理耗时（秒）")
    start_time: datetime = Field(description="开始处理时间")
    end_time: Optional[datetime] = Field(default=None, description="结束处理时间")
    
    # 配置信息
    config_snapshot: Dict[str, Any] = Field(description="处理时的配置快照")
    
    @property
    def is_completed(self) -> bool:
        """是否完全完成"""
        return self.completed_count >= self.planned_count
    
    @property
    def total_materials_size_mb(self) -> float:
        """所有素材总大小（MB）"""
        return sum(m.size_mb for m in self.materials)
    
    @property
    def average_material_duration(self) -> float:
        """平均素材时长"""
        if not self.materials:
            return 0.0
        return sum(m.duration for m in self.materials) / len(self.materials)
    
    @property
    def actual_processing_time(self) -> float:
        """实际处理时间（从开始到结束）"""
        if not self.end_time:
            return 0.0
        return (self.end_time - self.start_time).total_seconds()
    
    @property
    def processing_time_minutes(self) -> float:
        """处理耗时（分钟）"""
        return self.processing_time / 60
    
    @property
    def processing_efficiency(self) -> float:
        """处理效率（素材时长/处理时间）"""
        if self.processing_time == 0:
            return 0.0
        total_material_duration = sum(m.duration for m in self.materials)
        return total_material_duration / self.processing_time


class ProcessingSession(BaseModel):
    """单次处理会话记录"""
    session_id: str = Field(description="会话ID（时间戳）")
    start_time: datetime = Field(description="会话开始时间")
    end_time: Optional[datetime] = Field(default=None, description="会话结束时间")
    
    # 处理结果
    dramas: List[DramaRecord] = Field(default_factory=list, description="处理的短剧列表")
    total_dramas: int = Field(description="总处理短剧数")
    successful_dramas: int = Field(description="成功处理短剧数")
    total_materials: int = Field(description="总生成素材数")
    
    # 环境信息
    command_line: str = Field(description="执行的命令行")
    config_file: Optional[str] = Field(default=None, description="使用的配置文件")
    source_directory: str = Field(description="源素材目录")
    output_directory: str = Field(description="输出根目录")
    
    # 统计信息
    total_processing_time: float = Field(description="总处理时间（秒）")
    total_size_mb: float = Field(description="总生成文件大小（MB）")
    
    @property
    def success_rate(self) -> float:
        """会话成功率"""
        if self.total_dramas == 0:
            return 0.0
        return self.successful_dramas / self.total_dramas
    
    @property
    def duration_minutes(self) -> float:
        """会话持续时间（分钟）"""
        if not self.end_time:
            return 0.0
        return (self.end_time - self.start_time).total_seconds() / 60
    
    @property
    def actual_processing_time(self) -> float:
        """所有剧目的实际处理时间总和（秒）"""
        return sum(drama.processing_time for drama in self.dramas)
    
    @property
    def session_duration(self) -> float:
        """整个会话持续时间（秒）"""
        if not self.end_time:
            return 0.0
        return (self.end_time - self.start_time).total_seconds()
    
    @property
    def processing_overhead(self) -> float:
        """处理开销时间（会话时间 - 实际处理时间）"""
        return max(0, self.session_duration - self.actual_processing_time)
    
    @property
    def processing_efficiency_ratio(self) -> float:
        """处理效率比（实际处理时间/会话时间）"""
        if self.session_duration == 0:
            return 0.0
        return self.actual_processing_time / self.session_duration


class DailySummary(BaseModel):
    """日度汇总"""
    date: str = Field(description="日期（YYYY-MM-DD）")
    sessions: List[str] = Field(default_factory=list, description="会话ID列表")
    
    total_dramas: int = Field(description="当日处理短剧总数")
    successful_dramas: int = Field(description="成功处理短剧数")
    total_materials: int = Field(description="总生成素材数")
    total_size_mb: float = Field(description="总文件大小（MB）")
    total_processing_time: float = Field(description="总处理时间（秒）")
    
    unique_dramas: List[str] = Field(default_factory=list, description="当日处理的短剧名列表")
    
    @property
    def success_rate(self) -> float:
        """日度成功率"""
        if self.total_dramas == 0:
            return 0.0
        return self.successful_dramas / self.total_dramas


class MonthlySummary(BaseModel):
    """月度汇总"""
    year_month: str = Field(description="年月（YYYY-MM）")
    daily_summaries: List[str] = Field(default_factory=list, description="日期列表")
    
    total_dramas: int = Field(description="当月处理短剧总数")
    successful_dramas: int = Field(description="成功处理短剧数")
    total_materials: int = Field(description="总生成素材数")
    total_size_mb: float = Field(description="总文件大小（MB）")
    total_processing_time: float = Field(description="总处理时间（秒）")
    
    active_days: int = Field(description="活跃天数")
    unique_dramas: List[str] = Field(default_factory=list, description="当月处理的短剧名列表")
    
    @property
    def success_rate(self) -> float:
        """月度成功率"""
        if self.total_dramas == 0:
            return 0.0
        return self.successful_dramas / self.total_dramas
    
    @property
    def avg_dramas_per_day(self) -> float:
        """日均处理短剧数"""
        if self.active_days == 0:
            return 0.0
        return self.total_dramas / self.active_days


class AllTimeSummary(BaseModel):
    """全时段汇总"""
    first_session: Optional[datetime] = Field(default=None, description="首次使用时间")
    last_session: Optional[datetime] = Field(default=None, description="最近使用时间")
    
    total_sessions: int = Field(description="总会话数")
    total_dramas: int = Field(description="总处理短剧数")
    successful_dramas: int = Field(description="成功处理短剧数")
    total_materials: int = Field(description="总生成素材数")
    total_size_mb: float = Field(description="总文件大小（MB）")
    total_processing_time: float = Field(description="总处理时间（秒）")
    
    unique_dramas: List[str] = Field(default_factory=list, description="所有处理过的短剧名")
    active_days: int = Field(description="总活跃天数")
    
    @property
    def success_rate(self) -> float:
        """整体成功率"""
        if self.total_dramas == 0:
            return 0.0
        return self.successful_dramas / self.total_dramas
    
    @property
    def avg_dramas_per_session(self) -> float:
        """每会话平均处理短剧数"""
        if self.total_sessions == 0:
            return 0.0
        return self.total_dramas / self.total_sessions
    
    @property
    def total_processing_hours(self) -> float:
        """总处理时长（小时）"""
        return self.total_processing_time / 3600
