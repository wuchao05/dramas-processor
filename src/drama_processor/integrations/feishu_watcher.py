"""Feishu watcher that polls pending dramas and triggers processing automatically."""

import logging
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional
from datetime import datetime

from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass
from threading import Event
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
        self.executor = ThreadPoolExecutor(max_workers=self.max_dates)
        self._wake_event = Event()
        self.active_tasks: Dict[str, "DateTask"] = {}
    
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
                
                # 等待下一次轮询，如期间有剧目完成会立即唤醒
                if self._wake_event.wait(timeout=self.poll_interval):
                    self._wake_event.clear()
        finally:
            if run_once:
                self._wait_for_tasks()
            self._stop = True
            self._cancel_all_tasks()
            self.executor.shutdown(wait=True, cancel_futures=False)
    
    def stop(self) -> None:
        """Request watcher stop."""
        self._stop = True
        self._cancel_all_tasks()
    
    # Internal helpers -----------------------------------------------------
    
    def _notify(self, message: str) -> None:
        if self.echo:
            self.echo(message)
        else:
            logger.info(message)

    def _create_client(self) -> FeishuClient:
        """Create a new Feishu client instance for worker threads."""
        return FeishuClient(self.base_config.feishu)
    
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
    
    def _priority_value(self, date_str: str, full_date: Optional[str] = None) -> tuple:
        """Compute priority for given date (lower tuple => higher priority)."""
        today = datetime.now().date()
        try:
            # 优先使用 full_date（完整日期格式），避免年份猜测问题
            if full_date and "-" in full_date:
                target = datetime.strptime(full_date, "%Y-%m-%d").date()
            elif "-" in date_str:
                target = datetime.strptime(date_str, "%Y-%m-%d").date()
            elif "." in date_str:
                # 简化格式，需要猜测年份（仅作为后备方案）
                month, day = date_str.split(".", 1)
                month_int = int(month)
                day_int = int(day)
                
                # 跨年判断：先按当前年份解析，如果日期在过去超过180天（约6个月），则认为是明年
                year = today.year
                try:
                    temp_date = datetime(year, month_int, day_int).date()
                    days_diff = (today - temp_date).days
                    # 如果日期在过去超过180天，认为是明年的日期
                    if days_diff > 180:
                        year = today.year + 1
                except ValueError:
                    # 日期无效（如2月30日），保持当前年份
                    pass
                
                target = datetime(year, month_int, day_int).date()
            else:
                raise ValueError
        except Exception:
            return (2, 9999, date_str)
        delta = (target - today).days
        group = 0 if delta <= 0 else 1  # 今天或已过期优先，其次未来日期
        return (group, abs(delta), date_str)
    
    def _start_date_task(self, date_label: str, initial_info: Dict[str, Dict[str, str]], priority: tuple) -> None:
        cancel_event = Event()
        client = self._create_client()
        future = self.executor.submit(self._process_date, date_label, initial_info, cancel_event, client)
        self.active_tasks[date_label] = DateTask(future=future, cancel_event=cancel_event, priority=priority)
        self._notify(f"🚀 启动日期 {date_label} 任务，优先级 {priority}")
    
    def _cancel_task(self, date_label: str) -> None:
        task = self.active_tasks.get(date_label)
        if not task:
            return
        task.cancel_event.set()
        self._notify(f"⏹️ 正在停止日期 {date_label} 任务...")
        try:
            # 等待任务结束（允许其完成当前素材后退出）
            task.future.result(timeout=5)
        except Exception:
            pass
        finally:
            self.active_tasks.pop(date_label, None)
    
    def _cancel_all_tasks(self) -> None:
        for date_label in list(self.active_tasks.keys()):
            self._cancel_task(date_label)
    
    def _wait_for_tasks(self) -> None:
        for date_label, task in list(self.active_tasks.items()):
            try:
                task.future.result()
            except Exception:
                pass
    
    def _cleanup_finished_tasks(self) -> None:
        """清理已完成的任务，并在任务完成时立即触发下一次轮询"""
        tasks_cleaned = False
        for date_label, task in list(self.active_tasks.items()):
            if task.future.done():
                try:
                    task.future.result()
                    self._notify(f"✅ 日期 {date_label} 任务已完成")
                except Exception as exc:
                    logger.error(f"❌ 日期 {date_label} 任务异常结束: {exc}")
                    self._notify(f"❌ 日期 {date_label} 任务异常结束：{exc}")
                self.active_tasks.pop(date_label, None)
                tasks_cleaned = True
        
        # 如果有任务完成，立即唤醒主循环进行下一次轮询（查找其他日期的待剪辑剧）
        if tasks_cleaned:
            self._notify("🔄 日期任务完成，立即查找其他日期的待剪辑剧...")
            self._wake_event.set()
    
    def _get_lowest_priority_date(self) -> Optional[str]:
        if not self.active_tasks:
            return None
        return max(self.active_tasks.items(), key=lambda item: item[1].priority)[0]
    
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
        # 首先清理已完成的任务（这样可以立即发现新的空闲槽位）
        self._cleanup_finished_tasks()
        
        # 如果还有活跃任务在运行，跳过本次查询，避免在剪辑过程中打印查询日志
        if self.active_tasks:
            return True  # 返回 True 表示有活动，避免触发 idle_exit
        
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
        if grouped:
            summary = ", ".join(f"{date}:{len(items)}部" for date, items in grouped.items())
            self._notify(f"📚 分组结果：{summary}")
        target_dates = self._select_dates(grouped)
        if not target_dates:
            self._notify("📭 没有符合过滤条件的日期任务")
            return False
        processed_any = bool(self.active_tasks)
        for date_label in target_dates:
            if self._stop:
                break
            if date_label in self.active_tasks:
                continue
            initial_info = dict(grouped.get(date_label, {}))
            # 从该日期组的剧集中获取 full_date（所有剧集的 full_date 应该一致）
            full_date = None
            if initial_info:
                first_drama_info = next(iter(initial_info.values()))
                full_date = first_drama_info.get("full_date")
            priority = self._priority_value(date_label, full_date)
            if len(self.active_tasks) < self.max_dates:
                self._start_date_task(date_label, initial_info, priority)
                processed_any = True
            else:
                worst_date = self._get_lowest_priority_date()
                if worst_date and priority < self.active_tasks[worst_date].priority:
                    self._notify(f"⏹️ 为优先日期 {date_label}，准备停止 {worst_date} 任务")
                    self._cancel_task(worst_date)
                    self._start_date_task(date_label, initial_info, priority)
                    processed_any = True
        return processed_any
    
    def _group_by_date(self, drama_info: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, Dict[str, str]]]:
        grouped: Dict[str, Dict[str, Dict[str, str]]] = {}
        for drama_name, info in drama_info.items():
            date_label = info.get("date") or "未知日期"
            grouped.setdefault(date_label, {})[drama_name] = info
        
        # 对每个日期组内的剧按优先级排序：
        # 1. 评级为优先级标签（如"红标"）的最优先
        # 2. 相同评级的剧按上架时间排序（可配置升序/降序）
        priority_rating = self.base_config.feishu.priority_rating_value if self.base_config.feishu else "红标"
        sort_desc = self.base_config.feishu.upload_time_sort_desc if self.base_config.feishu else True
        
        for date_label in grouped:
            all_dramas = []
            
            for drama_name, info in grouped[date_label].items():
                upload_time = info.get("upload_time") or 0  # 没有上架时间的设为0
                rating = info.get("rating") or ""
                is_priority = (rating == priority_rating)  # 优先级标签为 True，其他为 False
                all_dramas.append((drama_name, info, is_priority, upload_time))
            
            # 排序：先按优先级标签（True在前），再按上架时间（升序或降序）
            if sort_desc:
                # 降序：时间戳越大越靠前（新的优先）
                all_dramas.sort(key=lambda x: (not x[2], -x[3]))
            else:
                # 升序：时间戳越小越靠前（早的优先）
                all_dramas.sort(key=lambda x: (not x[2], x[3]))
            
            # 重新构建该日期的字典
            sorted_dict = {}
            for drama_name, info, _, _ in all_dramas:
                sorted_dict[drama_name] = info
            
            grouped[date_label] = sorted_dict
        
        return dict(sorted(grouped.items(), key=lambda item: self._date_sort_key(item[0])))
    
    def _select_dates(self, grouped: Dict[str, Dict[str, Dict[str, str]]]) -> List[str]:
        dates = list(grouped.keys())
        if self.date_whitelist:
            dates = [d for d in dates if d in self.date_whitelist]
        if self.date_blacklist:
            dates = [d for d in dates if d not in self.date_blacklist]
        return dates
    
    def _process_date(self, date_label: str, initial_info: Dict[str, Dict[str, str]], cancel_event: Event, client: FeishuClient) -> bool:
        """Process a single date batch using the provided initial data."""
        self._notify(f"🎯 日期 {date_label} 检测到待剪辑剧，开始处理")
        processed_any = False
        try:
            self._run_batch(date_label, initial_info or {}, client, cancel_event)
            processed_any = True
        except Exception as exc:  # pylint: disable=broad-except
            logger.error(f"❌ 日期 {date_label} 处理失败: {exc}")
            self._notify(f"❌ 日期 {date_label} 处理失败：{exc}")
        return processed_any
    
    def _fetch_date_tasks(self, date_label: str, client: Optional[FeishuClient] = None) -> Dict[str, Dict[str, str]]:
        """Fetch pending dramas for a specific date."""
        client_obj = client or self.client
        date_filter = None
        if date_label and date_label not in ("未知", "未知日期"):
            try:
                date_filter = _convert_date_format(date_label)
            except ValueError:
                date_filter = None
        
        try:
            info = client_obj.get_pending_dramas_with_dates(
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
    
    def _run_batch(self, date_label: str, initial_info: Dict[str, Dict[str, str]], client: FeishuClient, cancel_event: Event) -> None:
        """Process dramas of a specific date one by one with live synchronization."""
        processed = set()
        self._notify(f"🎯 日期 {date_label} 首次检测到 {len(initial_info)} 部待剪辑剧")
        idle_rounds = 0
        cached_info = dict(initial_info)
        
        while not self._stop:
            if cancel_event.is_set():
                self._notify(f"⏹️ 日期 {date_label} 任务收到停止信号，结束")
                self._wake_event.set()
                break
            if cached_info is not None:
                current_info = cached_info
                cached_info = None
            else:
                current_info = self._fetch_date_tasks(date_label, client)
            
            # 仅保留尚未处理、仍为待剪辑状态的数据
            pending = {
                name: info for name, info in current_info.items()
                if name not in processed
            }
            
            if not pending:
                idle_rounds += 1
                if idle_rounds >= self.settle_rounds:
                    self._notify(f"✅ 日期 {date_label} 暂无新的待剪辑剧，结束本轮处理")
                    self._wake_event.set()
                    break
                self._sleep_with_cancel(self.settle_seconds)
                continue
            
            idle_rounds = 0
            # 仅取一个剧目处理，剩余的留待下一轮，以便实时检测变动
            drama_name, info = next(iter(pending.items()))
            if self._stop:
                break
            if cancel_event.is_set():
                self._notify(f"⏹️ 日期 {date_label} 任务收到停止信号，结束")
                self._wake_event.set()
                break
            
            latest_snapshot = self._fetch_date_tasks(date_label, client)
            if drama_name not in latest_snapshot:
                self._notify(f"⏭️ 侦测到 '{drama_name}' 已不在 {date_label} 待剪辑列表，跳过")
                processed.add(drama_name)
                cached_info = None
                continue
            
            try:
                processed_ok = self._process_single_drama(date_label, drama_name, info, client, cancel_event)
            except Exception as exc:  # pylint: disable=broad-except
                logger.error(f"❌ 剧目 {drama_name} 处理失败: {exc}")
                self._notify(f"❌ '{drama_name}' 处理失败：{exc}")
                processed_ok = False
            finally:
                processed.add(drama_name)
                cached_info = None
            
            if not processed_ok:
                self._notify(f"⏭️ '{drama_name}' 本地未找到可处理的目录，跳过并继续下一个剧目/日期")
                continue
            
            if self._stop:
                break
        self._wake_event.set()
    def _process_single_drama(self, date_label: str, drama_name: str, info: Dict[str, str], client: FeishuClient, cancel_event: Event) -> bool:
        """Process a single drama extracted from Feishu."""
        if cancel_event.is_set():
            self._wake_event.set()
            return False
        config_copy = self.base_config.copy(deep=True)
        config_copy.include = [drama_name]
        config_copy.exclude = None
        config_copy.full = False
        config_copy.no_interactive = True
        
        root_path = Path(config_copy.get_actual_source_dir())
        if not root_path.exists():
            raise FileNotFoundError(f"源素材目录不存在: {root_path}")
        
        record_id = info.get("record_id")
        
        def status_update_callback(drama: str, new_status: str):
            if drama != drama_name or not record_id:
                return "SKIP"
            try:
                success = client.update_record_status(record_id, new_status)
                return True if success else False
            except FeishuRecordNotFoundError as exc:
                logger.warning(f"⚠️ 记录 {record_id} 未找到，跳过 '{drama_name}'：{exc}")
                return "SKIP"
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning(f"⚠️ 更新 '{drama_name}' 状态失败: {exc}")
                return False
        
        processor = DramaProcessor(config_copy, status_callback=status_update_callback)
        drama_dates = {drama_name: info.get("date", date_label)}
        
        self._notify(f"🎬 开始处理 {date_label} - {drama_name}")
        total_done, total_planned = processor.process_all_dramas(str(root_path), drama_dates)
        if total_planned == 0:
            self._notify(f"⚠️ 未找到 '{drama_name}' 对应的本地剧集目录，跳过")
            missing_status = None
            if self.base_config.feishu:
                missing_status = getattr(self.base_config.feishu, "missing_source_status_value", None)
            missing_status = missing_status or "无源视频"
            if record_id:
                try:
                    if client.update_record_status(record_id, missing_status):
                        self._notify(f"📝 已将 '{drama_name}' 状态更新为 '{missing_status}'")
                except Exception as exc:  # pylint: disable=broad-except
                    logger.warning(f"⚠️ 更新 '{drama_name}' 缺失状态失败: {exc}")
            self._wake_event.set()
            return False
        self._notify(f"✅ {drama_name} 完成：{total_done}/{total_planned} 条素材")
        self._wake_event.set()
        return True
@dataclass
class DateTask:
    """Track an active date processing task."""
    future: Future
    cancel_event: Event
    priority: tuple
