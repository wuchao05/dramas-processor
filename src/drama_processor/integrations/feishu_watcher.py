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
        subject_filter: Optional[str] = None,
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
        self.subject_filter = subject_filter
        self.idle_exit_minutes = idle_exit_minutes
        self.state_dir = Path(state_dir or config.feishu_watcher.state_dir or "history/feishu_watcher")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.wake_signal_path = self.state_dir / "wake-now.signal"
        self._stop = False
        self.last_activity = time.time()
        self.executor = ThreadPoolExecutor(max_workers=self.max_dates)
        self._wake_event = Event()
        self.active_tasks: Dict[str, "DateTask"] = {}
        # 评级优先级改为跟随默认配置能力，而不是达人配置。
        self.enable_rating_priority = bool(config.feishu.priority_rating_value)
    
    def run(self, run_once: bool = False) -> None:
        """Start the watcher."""
        filter_info = f"状态过滤={self.status_filter}"
        if self.subject_filter:
            filter_info += f"，主体过滤={self.subject_filter}"
        self._notify(f"🚀 启动飞书轮询：每 {self.poll_interval}s 轮询一次，{filter_info}")
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
                
                # 等待下一次轮询，如期间有剧目完成或外部触发会立即唤醒
                self._wait_for_next_poll()
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

    def _consume_external_wake_signal(self) -> bool:
        if not self.wake_signal_path.exists():
            return False

        try:
            self.wake_signal_path.unlink()
        except FileNotFoundError:
            return False

        self._notify("⚡ 收到立即查询指令，马上开始下一轮飞书查询")
        return True

    def _wait_for_next_poll(self) -> None:
        if self._consume_external_wake_signal():
            return

        deadline = time.time() + self.poll_interval
        while not self._stop:
            if self._wake_event.wait(timeout=1):
                self._wake_event.clear()
                return

            if self._consume_external_wake_signal():
                self._wake_event.clear()
                return

            if time.time() >= deadline:
                return
    
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

    def _get_priority_rating_value(self) -> str:
        if not self.base_config.feishu:
            return "红标"
        return (self.base_config.feishu.priority_rating_value or "红标").strip()

    @staticmethod
    def _normalize_rating_value(rating: Optional[str]) -> str:
        return (rating or "").strip()

    def _get_primary_rating_priority(self, rating: Optional[str]) -> int:
        if not self.enable_rating_priority:
            return 0
        return 0 if self._normalize_rating_value(rating) == self._get_priority_rating_value() else 1

    def _get_secondary_rating_priority(self, rating: Optional[str]) -> int:
        if not self.enable_rating_priority:
            return 0

        normalized = self._normalize_rating_value(rating)
        if normalized == self._get_priority_rating_value():
            return 0
        if normalized == "绿标":
            return 1
        if normalized == "黄标":
            return 2
        return 99

    @staticmethod
    def _get_upload_time_sort_key(upload_time: Optional[int], descending: bool = False) -> tuple:
        if isinstance(upload_time, int) and upload_time > 0:
            return (0, -upload_time if descending else upload_time)
        return (1, 0)

    def _priority_value(self, date_str: str, full_date: Optional[str] = None) -> tuple:
        """将飞书日期转换为从早到晚的排序键。"""
        try:
            if full_date and "-" in full_date:
                target = datetime.strptime(full_date, "%Y-%m-%d").date()
            elif "-" in date_str:
                target = datetime.strptime(date_str, "%Y-%m-%d").date()
            elif "." in date_str:
                month, day = date_str.split(".", 1)
                target = datetime(datetime.now().year, int(month), int(day)).date()
            else:
                raise ValueError
        except Exception:
            return (1, 9999, 12, 31, date_str)
        return (0, target.year, target.month, target.day, date_str)

    def _build_drama_sort_key(
        self,
        drama_name: str,
        info: Dict[str, str],
        date_label: Optional[str] = None,
        include_date: bool = True,
    ) -> tuple:
        rating = info.get("rating")
        is_priority_rating = self._get_primary_rating_priority(rating) == 0
        sort_key = [0 if is_priority_rating else 1]
        date_sort_key = self._priority_value(
            date_label or info.get("date") or "未知日期",
            info.get("full_date"),
        )

        if is_priority_rating:
            sort_key.append(
                self._get_upload_time_sort_key(
                    info.get("upload_time"),
                    descending=True,
                )
            )
            if include_date:
                sort_key.append(date_sort_key)
            sort_key.append(drama_name)
            return tuple(sort_key)

        if include_date:
            sort_key.append(date_sort_key)
        sort_key.extend(
            [
                self._get_secondary_rating_priority(rating),
                self._get_upload_time_sort_key(
                    info.get("upload_time"),
                    descending=True,
                ),
                drama_name,
            ]
        )
        return tuple(sort_key)
    
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
        if self.active_tasks:
            logger.info(f"🔍 检查已完成任务，当前活跃任务数：{len(self.active_tasks)}")
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
    
    def _get_all_sorted_dramas(self, drama_info: Dict[str, Dict[str, str]]) -> List[tuple]:
        """将所有待剪辑的剧全局排序，返回 [(drama_name, info, date_label, priority), ...]"""
        grouped = self._group_by_date(drama_info)
        if not grouped:
            return []

        dates = self._select_dates(grouped)
        if not dates:
            return []

        all_sorted = []
        for date_label in dates:
            dramas_in_date = grouped[date_label]
            if not dramas_in_date:
                continue

            for drama_name, info in dramas_in_date.items():
                combined_priority = self._build_drama_sort_key(
                    drama_name,
                    info,
                    date_label=date_label,
                    include_date=True,
                )
                all_sorted.append((drama_name, info, date_label, combined_priority))

        all_sorted.sort(key=lambda x: x[3])
        return all_sorted
    
    def _poll_once(self) -> bool:
        """
        查询并处理所有待剪辑的剧。
        
        工作流程：
        1. 查询飞书，获取所有待剪辑的剧
        2. 红标剧优先；多个红标时，先按上架时间从晚到早，再按日期从早到晚
        3. 红标处理完后，再处理非红标剧；非红标先按日期从早到晚，同日期内按绿标、黄标、上架时间、剧名排序
        4. 选择优先级最高的一部剧处理
        5. 处理完后，回到步骤1，重新查询和排序
        6. 如果所有剧都处理完，等待 settle_seconds 后再查一次（防止飞书数据同步延迟）
        7. 如果连续 settle_rounds 次都没有新剧，退出，依赖外层 run() 的 poll_interval 轮询
        
        Returns:
            bool: 是否处理了至少一部剧
        """
        self._notify("🔍 查询飞书，获取所有待剪辑的剧...")
        
        # 记录已处理的剧名
        processed = set()
        idle_rounds = 0
        
        while not self._stop:
            # 查询飞书获取最新待剪辑剧
            try:
                drama_info = self.client.get_pending_dramas_with_dates(
                    status_filter=self.status_filter, 
                    subject_filter=self.subject_filter,
                    include_rating=self.enable_rating_priority
                )
            except Exception as exc:
                logger.error(f"获取待剪辑剧失败: {exc}")
                self._notify(f"⚠️ 获取待剪辑剧失败：{exc}")
                break
            
            if not drama_info:
                if not processed:
                    self._notify("📭 当前没有待剪辑的剧")
                else:
                    self._notify("✅ 所有待剪辑的剧已处理完成，暂无新剧")
                break
            
            # 全局排序所有待剪辑的剧
            all_sorted = self._get_all_sorted_dramas(drama_info)
            if not all_sorted:
                self._notify("✅ 没有符合条件的待剪辑剧")
                break
            
            # 第一次查询时，打印排序结果
            if not processed:
                self._notify(f"📊 检测到 {len(all_sorted)} 部待剪辑剧，按优先级处理")
                logger.info("📋 全局优先级排序结果（前10）：")
                for idx, (drama_name, info, date_label, _) in enumerate(all_sorted[:10], 1):
                    rating = info.get("rating") or "未标记"
                    upload_time = info.get("upload_time") or 0
                    upload_date_str = "未知"
                    if upload_time:
                        try:
                            upload_date = datetime.fromtimestamp(upload_time / 1000)
                            upload_date_str = upload_date.strftime("%m.%d %H:%M")
                        except Exception:
                            pass
                    logger.info(
                        f"  {idx}. [{date_label}] {drama_name} - 评级: {rating} - 上架时间: {upload_date_str}"
                    )
            
            # 过滤掉已处理的剧
            pending = [d for d in all_sorted if d[0] not in processed]
            
            if not pending:
                idle_rounds += 1
                if idle_rounds >= self.settle_rounds:
                    if self.settle_rounds == 0:
                        self._notify("✅ 所有待剪辑的剧已处理完成，进入外层轮询")
                    else:
                        self._notify(f"✅ 所有待剪辑的剧已处理完成（连续{idle_rounds}次查询无新剧）")
                    break
                self._notify(f"⏸️ 暂无新剧，{self.settle_seconds}秒后重新查询（{idle_rounds}/{self.settle_rounds}）...")
                self._sleep_with_cancel(self.settle_seconds)
                continue
            
            idle_rounds = 0
            
            # 选择优先级最高的剧
            drama_name, info, date_label, _ = pending[0]
            
            self._notify(f"🎯 选择处理：[{date_label}] {drama_name}")
            
            # 再次检查该剧是否仍在待剪辑列表中（双重确认）
            latest_info = self.client.get_pending_dramas_with_dates(
                status_filter=self.status_filter,
                subject_filter=self.subject_filter,
                include_rating=self.enable_rating_priority
            )
            if drama_name not in latest_info:
                self._notify(f"⏭️ '{drama_name}' 已不在待剪辑列表，跳过")
                processed.add(drama_name)
                continue
            
            # 处理这部剧
            try:
                cancel_event = Event()  # 创建一个临时的取消事件
                processed_ok = self._process_single_drama(date_label, drama_name, info, self.client, cancel_event)
            except Exception as exc:
                logger.error(f"❌ 剧目 {drama_name} 处理失败: {exc}")
                self._notify(f"❌ '{drama_name}' 处理失败：{exc}")
                processed_ok = False
            finally:
                processed.add(drama_name)
            
            if not processed_ok:
                self._notify(f"⏭️ '{drama_name}' 处理失败，继续下一部剧")
        
        # 返回是否处理了至少一部剧
        return len(processed) > 0
    
    def _group_by_date(self, drama_info: Dict[str, Dict[str, str]], verbose: bool = True) -> Dict[str, Dict[str, Dict[str, str]]]:
        grouped: Dict[str, Dict[str, Dict[str, str]]] = {}
        for drama_name, info in drama_info.items():
            date_label = info.get("date") or "未知日期"
            grouped.setdefault(date_label, {})[drama_name] = info
        
        # 日期组内排序：
        # 1. 红标优先
        # 2. 非红标内再按绿标、黄标、其他评级排序
        # 3. 同评级时按上架时间从晚到早，再按剧名字典序兜底
        for date_label in grouped:
            all_dramas = []
            
            for drama_name, info in grouped[date_label].items():
                all_dramas.append((drama_name, info))
            
            all_dramas.sort(
                key=lambda item: self._build_drama_sort_key(
                    item[0],
                    item[1],
                    date_label=date_label,
                    include_date=False,
                )
            )
            
            # 调试日志：打印排序后的顺序（仅在 verbose=True 时打印）
            if verbose and all_dramas:
                logger.info(f"📊 日期 {date_label} 内的剧集排序结果：")
                for idx, (drama_name, info) in enumerate(all_dramas, 1):
                    rating = info.get("rating") or "未标记"
                    upload_time = info.get("upload_time") or 0
                    upload_date_str = "未知"
                    if upload_time:
                        try:
                            upload_date = datetime.fromtimestamp(upload_time / 1000)
                            upload_date_str = upload_date.strftime("%m.%d %H:%M")
                        except Exception:
                            pass
                    logger.info(
                        f"  {idx}. {drama_name} - 评级: {rating} - 上架时间: {upload_date_str}"
                    )
            
            # 重新构建该日期的字典
            sorted_dict = {}
            for drama_name, info in all_dramas:
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
                subject_filter=self.subject_filter,
                date_filter=date_filter,
                include_rating=self.enable_rating_priority
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
                # 重新查询飞书并排序
                raw_info = self._fetch_date_tasks(date_label, client)
                # 对查询结果进行排序（与 _group_by_date 保持一致，但不打印排序日志避免重复）
                grouped = self._group_by_date({name: info for name, info in raw_info.items()}, verbose=False)
                current_info = grouped.get(date_label, {})
            
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
                # 每处理完一部剧（无论成功或失败），立即触发主循环重新查询飞书
                self._wake_event.set()
            
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
        
        # 应用飞书抖音素材配置（如果存在）
        if "douyin_config" in info and info["douyin_config"]:
            from ..utils.douyin_config_parser import parse_douyin_material_config
            
            logger.info(f"📱 检测到剧目 '{drama_name}' 有抖音素材配置，开始解析...")
            parsed = parse_douyin_material_config(info["douyin_config"])
            if parsed:
                logger.info(f"✅ 使用飞书抖音配置：{drama_name}, count={parsed['count']}")
                config_copy.brand_text_mapping = parsed["brand_text_mapping"]
                config_copy.count = parsed["count"]
            else:
                logger.warning(f"⚠️ 飞书抖音配置解析失败：{drama_name}，使用项目配置")
        else:
            logger.debug(f"剧目 '{drama_name}' 没有抖音素材配置，使用项目配置")
        
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
        drama_highlight_texts = (
            {drama_name: info["highlight_start_points"]}
            if info.get("highlight_start_points")
            else None
        )
        
        self._notify(f"🎬 开始处理 {date_label} - {drama_name}")
        total_done, total_planned = processor.process_all_dramas(
            str(root_path),
            drama_dates,
            drama_highlight_texts,
        )
        
        # 情况1：未找到本地剧集目录（total_planned == 0）
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
        
        # 情况2：有计划但实际生成为0（源素材不足）
        if total_done == 0 and total_planned > 0:
            self._notify(f"⚠️ '{drama_name}' 源素材不足，无法生成任何素材（计划 {total_planned} 条，实际 0 条）")
            failed_status = None
            if self.base_config.feishu:
                failed_status = getattr(self.base_config.feishu, "failed_status_value", None)
            failed_status = failed_status or "剪辑失败"
            remark = "请检查源素材目录中是否存在足额的源视频"
            if record_id:
                try:
                    if client.update_record_status(record_id, failed_status, remark=remark):
                        self._notify(f"📝 已将 '{drama_name}' 状态更新为 '{failed_status}'，备注：{remark}")
                except Exception as exc:  # pylint: disable=broad-except
                    logger.warning(f"⚠️ 更新 '{drama_name}' 失败状态失败: {exc}")
            self._wake_event.set()
            return False
        
        # 情况3：正常完成
        self._notify(f"✅ {drama_name} 完成：{total_done}/{total_planned} 条素材")
        self._wake_event.set()
        return True
@dataclass
class DateTask:
    """Track an active date processing task."""
    future: Future
    cancel_event: Event
    priority: tuple
