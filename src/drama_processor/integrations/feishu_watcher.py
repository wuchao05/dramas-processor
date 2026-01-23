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
        self._stop = False
        self.last_activity = time.time()
        self.executor = ThreadPoolExecutor(max_workers=self.max_dates)
        self._wake_event = Event()
        self.active_tasks: Dict[str, "DateTask"] = {}
        # 只有 xh-daily 用户才启用评级优先级功能
        self.enable_rating_priority = (config.active_user == "xh-daily")
    
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
        # 优先级排序：已过期(delta<0) > 今天(delta=0) > 未来(delta>0)
        # 在同一组内，按 delta 升序排序（越早的日期越优先）
        if delta < 0:
            # 已过期的日期：group=0，按 delta 排序（前天=-2 优先于 昨天=-1，因为 -2 < -1）
            return (0, delta, date_str)
        elif delta == 0:
            # 今天：group=1
            return (1, 0, date_str)
        else:
            # 未来的日期：group=2，按 delta 排序（明天=1 优先于 后天=2）
            return (2, delta, date_str)
    
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
        # 按日期分组并排序
        grouped = self._group_by_date(drama_info)
        if not grouped:
            return []
        
        # 过滤日期
        dates = self._select_dates(grouped)
        if not dates:
            return []
        
        # 将所有剧收集到一个列表中，附加日期和优先级信息
        all_sorted = []
        for date_label in dates:
            # 获取该日期的完整日期（用于优先级计算）
            dramas_in_date = grouped[date_label]
            if not dramas_in_date:
                continue
            
            first_drama_info = next(iter(dramas_in_date.values()))
            full_date = first_drama_info.get("full_date")
            date_priority = self._priority_value(date_label, full_date)
            
            # 按顺序遍历该日期内的剧（已经在 _group_by_date 中排好序了）
            for idx, (drama_name, info) in enumerate(dramas_in_date.items()):
                # 组合优先级：先按日期优先级，再按日期内顺序
                combined_priority = (date_priority, idx)
                all_sorted.append((drama_name, info, date_label, combined_priority))
        
        # 按组合优先级排序
        all_sorted.sort(key=lambda x: x[3])
        
        return all_sorted
    
    def _poll_once(self) -> bool:
        """
        查询并处理所有待剪辑的剧。
        
        工作流程：
        1. 查询飞书，获取所有待剪辑的剧
        2. 按日期优先级（越早越优先）+ 日期内上架时间（越早越优先）全局排序
        3. 选择优先级最高的一部剧处理
        4. 处理完后，回到步骤1，重新查询和排序
        5. 如果所有剧都处理完，等待 settle_seconds 后再查一次（防止飞书数据同步延迟）
        6. 如果连续 settle_rounds 次都没有新剧，退出，依赖外层 run() 的 poll_interval 轮询
        
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
                    upload_time = info.get("upload_time") or 0
                    upload_date_str = "未知"
                    if upload_time:
                        try:
                            upload_date = datetime.fromtimestamp(upload_time / 1000)
                            upload_date_str = upload_date.strftime("%m.%d %H:%M")
                        except Exception:
                            pass
                    logger.info(f"  {idx}. [{date_label}] {drama_name} - 上架时间: {upload_date_str}")
            
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
        
        # 对每个日期组内的剧按优先级排序：
        # 1. 如果启用评级优先级（xh-daily用户），按评级优先级：红标 > 绿标 > 黄标 > 其他
        # 2. 今天上架的剧优先于非今天上架的剧
        # 3. 在各自组内按上架时间升序排序（越早上架的越先处理）
        sort_desc = self.base_config.feishu.upload_time_sort_desc if self.base_config.feishu else True
        
        # 定义评级优先级映射（数值越小优先级越高）
        rating_priority_map = {
            "红标": 0,
            "绿标": 1,
            "黄标": 2,
        }
        
        # 获取今天的日期和当前小时（用于判断排序规则）
        now = datetime.now()
        today = now.date()
        current_hour = now.hour
        
        # 根据当前时间决定是新剧优先还是老剧优先
        # 0-10点：新剧（今天上架）优先
        # 10点之后：老剧（今天之前上架）优先
        prefer_new_dramas = current_hour < 10
        
        for date_label in grouped:
            all_dramas = []
            
            for drama_name, info in grouped[date_label].items():
                upload_time = info.get("upload_time") or 0  # 没有上架时间的设为0
                
                # 判断是否今天上架
                is_uploaded_today = False
                if upload_time:
                    try:
                        upload_date = datetime.fromtimestamp(upload_time / 1000).date()
                        is_uploaded_today = (upload_date == today)
                    except Exception:
                        pass
                
                # 只有启用评级优先级时才考虑评级，否则所有剧集评级优先级相同
                if self.enable_rating_priority:
                    rating = info.get("rating") or ""
                    rating_priority = rating_priority_map.get(rating, 999)  # 未定义的评级优先级最低
                else:
                    rating_priority = 0  # 所有剧集评级优先级相同
                
                all_dramas.append((drama_name, info, rating_priority, is_uploaded_today, upload_time))
            
            # 排序规则：
            # 1. 先按评级优先级（仅 xh-daily 用户）
            # 2. 根据当前时间决定新剧/老剧的优先级：
            #    - 0-10点：新剧（今天上架）优先，老剧（今天之前上架）次之
            #    - 10点之后：老剧（今天之前上架）优先，新剧（今天上架）次之
            # 3. 新剧按上架时间升序（越早上架越优先）
            # 4. 老剧按上架时间降序（越晚上架越优先）
            def sort_key(x):
                drama_name, info, rating_priority, is_uploaded_today, upload_time = x
                
                # 第1层：评级优先级
                layer1 = rating_priority
                
                # 第2层：根据时间段决定新剧/老剧优先级
                if prefer_new_dramas:
                    # 0-10点：新剧优先（is_uploaded_today=True 排前面）
                    layer2 = 0 if is_uploaded_today else 1
                else:
                    # 10点之后：老剧优先（is_uploaded_today=False 排前面）
                    layer2 = 1 if is_uploaded_today else 0
                
                # 第3层：上架时间排序
                # 新剧：升序（越早越优先，upload_time 越小越优先）
                # 老剧：降序（越晚越优先，upload_time 越大越优先，用负数实现）
                if is_uploaded_today:
                    layer3 = upload_time  # 升序
                else:
                    layer3 = -upload_time  # 降序（负数使大值排前面）
                
                return (layer1, layer2, layer3)
            
            all_dramas.sort(key=sort_key)
            
            # 调试日志：打印排序后的顺序（仅在 verbose=True 时打印）
            if verbose and all_dramas:
                time_mode = "0-10点模式（新剧优先）" if prefer_new_dramas else "10点后模式（老剧优先）"
                logger.info(f"📊 日期 {date_label} 内的剧集排序结果（{time_mode}）：")
                for idx, (drama_name, info, rating_priority, is_uploaded_today, upload_time) in enumerate(all_dramas, 1):
                    upload_date_str = "未知"
                    if upload_time:
                        try:
                            upload_date = datetime.fromtimestamp(upload_time / 1000)
                            upload_date_str = upload_date.strftime("%m.%d %H:%M")
                        except Exception:
                            pass
                    drama_type = "新剧" if is_uploaded_today else "老剧"
                    logger.info(f"  {idx}. {drama_name} - 上架时间: {upload_date_str}, {drama_type}")
            
            # 重新构建该日期的字典
            sorted_dict = {}
            for drama_name, info, _, _, _ in all_dramas:
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
        
        self._notify(f"🎬 开始处理 {date_label} - {drama_name}")
        total_done, total_planned = processor.process_all_dramas(str(root_path), drama_dates)
        
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
