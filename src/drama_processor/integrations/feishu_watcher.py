"""Feishu watcher that polls pending dramas and triggers processing automatically."""

import logging
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

from ..core.processor import DramaProcessor
from ..models.config import ProcessingConfig
from .feishu_client import FeishuClient, _convert_date_format, FeishuRecordNotFoundError


logger = logging.getLogger(__name__)


class FeishuWatcher:
    """Continuously poll Feishu and trigger processing jobs grouped by date."""
    
    def __init__(
        self,
        config: ProcessingConfig,
        poll_interval: Optional[int] = None,
        max_dates_per_cycle: Optional[int] = None,
        settle_seconds: Optional[int] = None,
        settle_rounds: Optional[int] = None,
        date_whitelist: Optional[List[str]] = None,
        date_blacklist: Optional[List[str]] = None,
        status_filter: Optional[str] = None,
        idle_exit_minutes: Optional[int] = None,
        state_dir: Optional[str] = None,
        echo: Optional[Callable[[str], None]] = None,
    ):
        if not config.feishu:
            raise ValueError("Feishu configuration is required to start the watcher")
        
        self.base_config = config
        self.client = FeishuClient(config.feishu)
        self.echo = echo
        self.poll_interval = max(60, poll_interval or 1800)
        self.max_dates = max(1, max_dates_per_cycle or 1)
        self.settle_seconds = max(10, settle_seconds or 120)
        self.settle_rounds = max(1, settle_rounds or 2)
        self.date_whitelist = self._normalize_date_list(date_whitelist)
        self.date_blacklist = set(self._normalize_date_list(date_blacklist) or [])
        self.status_filter = status_filter or config.feishu.pending_status_value
        self.idle_exit_minutes = idle_exit_minutes
        self.state_dir = Path(state_dir or config.feishu_watcher.state_dir or "history/feishu_watcher")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._stop = False
        self.last_activity = time.time()
    
    def run(self, run_once: bool = False) -> None:
        """Start the watcher."""
        self._notify(f"🚀 启动飞书轮询：每 {self.poll_interval}s 轮询一次，状态过滤={self.status_filter}")
        try:
            while not self._stop:
                processed = self._poll_once()
                if run_once:
                    break
                
                if processed:
                    self.last_activity = time.time()
                elif self.idle_exit_minutes:
                    idle_seconds = time.time() - self.last_activity
                    if idle_seconds >= self.idle_exit_minutes * 60:
                        self._notify("⏹️ 长时间未检测到待剪辑剧目，自动停止轮询")
                        break
                
                self._sleep_with_cancel(self.poll_interval)
        finally:
            self._stop = True
    
    def stop(self) -> None:
        """Request watcher stop."""
        self._stop = True
    
    # Internal helpers -----------------------------------------------------
    
    def _notify(self, message: str) -> None:
        if self.echo:
            self.echo(message)
        else:
            logger.info(message)
    
    @staticmethod
    def _normalize_date_list(items: Optional[List[str]]) -> Optional[List[str]]:
        if not items:
            return None
        normalized = []
        for item in items:
            item = (item or "").strip()
            if item:
                normalized.append(item)
        return normalized or None
    
    @staticmethod
    def _date_sort_key(date_str: str) -> tuple:
        """Provide a consistent sort key for date strings like '9.17'."""
        try:
            if "." in date_str:
                month, day = date_str.split(".", 1)
                return (int(month), int(day))
            if "-" in date_str:
                parts = date_str.split("-", 1)
                return (int(parts[0]), int(parts[1]))
        except ValueError:
            pass
        return (999, 999, date_str)
    
    def _sleep_with_cancel(self, duration: int) -> None:
        """Sleep with stop checking."""
        end_time = time.time() + duration
        while not self._stop and time.time() < end_time:
            time.sleep(1)
    
    def _poll_once(self) -> bool:
        """Fetch current pending records and trigger processing."""
        try:
            drama_info = self.client.get_pending_dramas_with_dates(status_filter=self.status_filter)
        except Exception as exc:
            logger.error(f"拉取飞书记录失败: {exc}")
            self._notify("⚠️ 无法从飞书获取待剪辑剧目，稍后重试")
            return False
        
        if not drama_info:
            self._notify("📭 当前没有待剪辑剧目")
            return False
        
        grouped = self._group_by_date(drama_info)
        target_dates = self._select_dates(grouped)
        if not target_dates:
            self._notify("📭 没有符合过滤条件的日期任务")
            return False
        
        processed_any = False
        for date_label in target_dates[: self.max_dates]:
            processed_any |= self._process_date(date_label)
            if self._stop:
                break
        return processed_any
    
    def _group_by_date(self, drama_info: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, Dict[str, str]]]:
        grouped: Dict[str, Dict[str, Dict[str, str]]] = {}
        for drama_name, info in drama_info.items():
            date_label = info.get("date") or "未知日期"
            grouped.setdefault(date_label, {})[drama_name] = info
        return dict(sorted(grouped.items(), key=lambda item: self._date_sort_key(item[0])))
    
    def _select_dates(self, grouped: Dict[str, Dict[str, Dict[str, str]]]) -> List[str]:
        dates = list(grouped.keys())
        if self.date_whitelist:
            dates = [d for d in dates if d in self.date_whitelist]
        if self.date_blacklist:
            dates = [d for d in dates if d not in self.date_blacklist]
        return dates
    
    def _process_date(self, date_label: str) -> bool:
        """Continuously process a single date until no new tasks appear."""
        self._notify(f"🎯 日期 {date_label} 检测到待剪辑剧，开始处理")
        idle_rounds = 0
        processed_any = False
        
        while not self._stop:
            date_tasks = self._fetch_date_tasks(date_label)
            if not date_tasks:
                idle_rounds += 1
                if idle_rounds >= self.settle_rounds:
                    self._notify(f"✅ 日期 {date_label} 暂无新的待剪辑剧，进入待命")
                    break
                self._sleep_with_cancel(self.settle_seconds)
                continue
            
            idle_rounds = 0
            processed_any = True
            try:
                self._run_batch(date_label, date_tasks)
            except Exception as exc:  # pylint: disable=broad-except
                logger.error(f"❌ 日期 {date_label} 处理失败: {exc}")
                self._notify(f"❌ 日期 {date_label} 处理失败：{exc}")
            if self._stop:
                break
        
        return processed_any
    
    def _fetch_date_tasks(self, date_label: str) -> Dict[str, Dict[str, str]]:
        """Fetch pending dramas for a specific date."""
        date_filter = None
        if date_label and date_label not in ("未知", "未知日期"):
            try:
                date_filter = _convert_date_format(date_label)
            except ValueError:
                date_filter = None
        
        try:
            info = self.client.get_pending_dramas_with_dates(
                status_filter=self.status_filter,
                date_filter=date_filter
            )
        except Exception as exc:
            logger.error(f"获取日期 {date_label} 的待剪辑剧失败: {exc}")
            return {}
        
        if not date_filter:
            info = {
                name: data for name, data in info.items()
                if (data.get("date") or "未知日期") == date_label
            }
        return info
    
    def _run_batch(self, date_label: str, drama_info: Dict[str, Dict[str, str]]) -> None:
        """Run the actual processing for a batch of dramas."""
        config_copy = self.base_config.copy(deep=True)
        dramas = list(drama_info.keys())
        config_copy.include = dramas
        config_copy.exclude = None
        config_copy.full = False
        config_copy.no_interactive = True
        
        # Resolve root directory
        root_path = Path(config_copy.get_actual_source_dir())
        if not root_path.exists():
            raise FileNotFoundError(f"源素材目录不存在: {root_path}")
        
        drama_records = {name: info["record_id"] for name, info in drama_info.items()}
        
        def status_update_callback(drama_name: str, new_status: str):
            record_id = drama_records.get(drama_name)
            if not record_id:
                return "SKIP"
            try:
                success = self.client.update_record_status(record_id, new_status)
                return True if success else False
            except FeishuRecordNotFoundError as exc:
                logger.warning(f"⚠️ 记录 {record_id} 未找到，跳过 '{drama_name}'：{exc}")
                return "SKIP"
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning(f"⚠️ 更新 '{drama_name}' 状态失败: {exc}")
                return False
        
        processor = DramaProcessor(config_copy, status_callback=status_update_callback)
        drama_dates = {name: info.get("date", date_label) for name, info in drama_info.items()}
        
        self._notify(f"🚀 正在处理日期 {date_label} 的 {len(dramas)} 部剧 ...")
        total_done, total_planned = processor.process_all_dramas(str(root_path), drama_dates)
        self._notify(f"📦 日期 {date_label} 完成：{total_done}/{total_planned} 条素材")
