"""
飞书群通知功能模块
"""
import logging
import requests
import time
from typing import List, Dict, Any, Optional
from datetime import datetime
from ..models.config import ProcessingConfig

logger = logging.getLogger(__name__)


class FeishuNotificationError(Exception):
    """飞书通知异常"""
    pass


class FeishuNotifier:
    """飞书群通知器"""
    
    def __init__(self, webhook_url: str = None):
        """
        初始化飞书通知器
        
        Args:
            webhook_url: 飞书机器人webhook地址
        """
        self.webhook_url = webhook_url or "https://open.feishu.cn/open-apis/bot/v2/hook/6d2e64c2-a5b4-4f2e-b518-a8e314c4c355"
        self._last_request_time = 0
        self._min_request_interval = 1.0  # 最小请求间隔1秒，防抖
    
    def _parse_date_for_sort(self, date_str: str) -> tuple:
        """
        解析日期字符串为可排序的元组
        
        Args:
            date_str: 日期字符串，如 "9.6", "10.1" 等
            
        Returns:
            可排序的元组 (月, 日)
        """
        try:
            if "." in date_str:
                month, day = date_str.split(".", 1)
                return (int(month), int(day))
            else:
                # 其他格式，按字符串排序
                return (999, 999)
        except (ValueError, AttributeError):
            # 解析失败，排在最后
            return (999, 999)
    
    def _debounced_request(self, data: Dict[str, Any]) -> bool:
        """
        防抖请求函数
        
        Args:
            data: 请求数据
            
        Returns:
            是否发送成功
        """
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        
        if time_since_last < self._min_request_interval:
            sleep_time = self._min_request_interval - time_since_last
            time.sleep(sleep_time)
        
        try:
            headers = {
                'Content-Type': 'application/json',
                'Accept': '*/*',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'User-Agent': 'DramaProcessor/1.0.0'
            }
            
            logger.info(f"发送飞书通知到: {self.webhook_url}")
            response = requests.post(
                self.webhook_url,
                json=data,
                headers=headers,
                timeout=30
            )
            
            self._last_request_time = time.time()
            
            response.raise_for_status()
            result = response.json()
            
            if result.get('code') == 0:
                logger.info("飞书通知发送成功")
                return True
            else:
                logger.error(f"飞书通知发送失败: {result}")
                return False
                
        except requests.RequestException as e:
            logger.error(f"飞书通知请求失败: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"发送飞书通知异常: {str(e)}")
            return False
    
    def send_start_notification(self, dramas_info: List[Dict[str, Any]], config: ProcessingConfig) -> bool:
        """
        发送开始剪辑通知
        
        Args:
            dramas_info: 待剪辑剧目信息列表，每个包含 {name, date, status}
            config: 处理配置
            
        Returns:
            是否发送成功
        """
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            date_str = config.get_date_str() or datetime.now().strftime("%m.%d")
            
            # 按日期分组剧目
            dramas_by_date = {}
            for drama in dramas_info:
                drama_date = drama.get('date', date_str)
                if drama_date not in dramas_by_date:
                    dramas_by_date[drama_date] = []
                dramas_by_date[drama_date].append(drama)
            
            # 按日期排序
            sorted_dates = sorted(dramas_by_date.keys(), key=lambda x: self._parse_date_for_sort(x))
            
            # 构建按日期分组的剧目列表文本
            drama_list_text = ""
            overall_index = 1
            for date_key in sorted_dates:
                dramas_for_date = dramas_by_date[date_key]
                drama_list_text += f"\n📅 {date_key} ({len(dramas_for_date)}部):\n"
                for drama in dramas_for_date:
                    drama_name = drama.get('name', '未知')
                    # 使用配置中的待处理状态值作为默认值
                    default_status = config.feishu.pending_status_value if config.feishu else "待剪辑"
                    drama_status = drama.get('status', default_status)
                    drama_list_text += f"  {overall_index}. {drama_name} (状态: {drama_status})\n"
                    overall_index += 1
            
            # 构建通知内容
            content_text = f"""🎬 开始批量剪辑通知

📅 开始时间: {current_time}
📊 本次处理: {len(dramas_info)} 部短剧
📋 每部生成: {config.count} 条素材
⏱️ 时长范围: {config.min_duration}~{config.max_duration}秒

📝 待处理剧目:
{drama_list_text}
🔄 处理中，请稍候..."""

            request_data = {
                "msg_type": "text",
                "content": {
                    "text": content_text
                }
            }
            
            return self._debounced_request(request_data)
            
        except Exception as e:
            logger.error(f"构建开始通知失败: {str(e)}")
            return False
    
    def send_completion_notification(self, dramas_results: List[Dict[str, Any]], 
                                   total_materials: int, total_planned: int,
                                   processing_time: float) -> bool:
        """
        发送完成剪辑通知
        
        Args:
            dramas_results: 剧目处理结果列表，每个包含 {name, date, status, completed, planned, output_dir}
            total_materials: 总生成素材数
            total_planned: 总计划素材数
            processing_time: 总处理时间(秒)
            
        Returns:
            是否发送成功
        """
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            processing_hours = processing_time / 3600
            processing_minutes = processing_time / 60
            
            # 统计成功和失败的剧目
            successful_dramas = [d for d in dramas_results if d.get('completed', 0) > 0]
            failed_dramas = [d for d in dramas_results if d.get('completed', 0) == 0]
            
            # 按日期分组成功剧目
            success_by_date = {}
            for drama in successful_dramas:
                drama_date = drama.get('date', '未知')
                if drama_date not in success_by_date:
                    success_by_date[drama_date] = []
                success_by_date[drama_date].append(drama)
            
            # 按日期排序并构建成功剧目列表
            success_list_text = ""
            overall_success_index = 1
            sorted_success_dates = sorted(success_by_date.keys(), key=lambda x: self._parse_date_for_sort(x))
            for date_key in sorted_success_dates:
                dramas_for_date = success_by_date[date_key]
                success_list_text += f"\n📅 {date_key} ({len(dramas_for_date)}部):\n"
                for drama in dramas_for_date:
                    drama_name = drama.get('name', '未知')
                    completed = drama.get('completed', 0)
                    planned = drama.get('planned', 0)
                    status_emoji = "✅" if completed == planned else "⚠️"
                    success_list_text += f"  {overall_success_index}. {status_emoji} {drama_name} ({completed}/{planned}条)\n"
                    overall_success_index += 1
            
            # 按日期分组失败剧目
            failed_list_text = ""
            if failed_dramas:
                failed_by_date = {}
                for drama in failed_dramas:
                    drama_date = drama.get('date', '未知')
                    if drama_date not in failed_by_date:
                        failed_by_date[drama_date] = []
                    failed_by_date[drama_date].append(drama)
                
                # 按日期排序并构建失败剧目列表
                overall_failed_index = 1
                sorted_failed_dates = sorted(failed_by_date.keys(), key=lambda x: self._parse_date_for_sort(x))
                for date_key in sorted_failed_dates:
                    dramas_for_date = failed_by_date[date_key]
                    failed_list_text += f"\n📅 {date_key} ({len(dramas_for_date)}部):\n"
                    for drama in dramas_for_date:
                        drama_name = drama.get('name', '未知')
                        failed_list_text += f"  {overall_failed_index}. ❌ {drama_name}\n"
                        overall_failed_index += 1
            
            # 构建时间显示
            if processing_hours >= 1:
                time_display = f"{processing_hours:.1f} 小时"
            else:
                time_display = f"{processing_minutes:.1f} 分钟"
            
            # 构建通知内容
            content_text = f"""🎉 批量剪辑完成通知

📅 完成时间: {current_time}
⏱️ 总耗时: {time_display}
📊 处理结果: {total_materials}/{total_planned} 条素材生成成功
📈 成功率: {(total_materials/max(total_planned, 1)*100):.1f}%

✅ 成功处理 ({len(successful_dramas)} 部):
{success_list_text}"""

            if failed_dramas:
                content_text += f"""
❌ 处理失败 ({len(failed_dramas)} 部):
{failed_list_text}"""

            content_text += f"""
📤 提醒: 请及时上传已完成的素材到形天素材库！"""

            request_data = {
                "msg_type": "text",
                "content": {
                    "text": content_text
                }
            }
            
            return self._debounced_request(request_data)
            
        except Exception as e:
            logger.error(f"构建完成通知失败: {str(e)}")
            return False
    
    def send_error_notification(self, error_message: str, dramas_info: List[Dict[str, Any]] = None) -> bool:
        """
        发送错误通知
        
        Args:
            error_message: 错误消息
            dramas_info: 相关剧目信息(可选)
            
        Returns:
            是否发送成功
        """
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            content_text = f"""❌ 剪辑处理异常通知

📅 时间: {current_time}
🚨 错误: {error_message}"""

            if dramas_info:
                content_text += f"""
📝 相关剧目: {', '.join([d.get('name', '未知') for d in dramas_info[:5]])}"""
                if len(dramas_info) > 5:
                    content_text += f" 等{len(dramas_info)}部"

            content_text += "\n\n请检查处理日志并手动处理相关问题。"

            request_data = {
                "msg_type": "text",
                "content": {
                    "text": content_text
                }
            }
            
            return self._debounced_request(request_data)
            
        except Exception as e:
            logger.error(f"构建错误通知失败: {str(e)}")
            return False


def create_feishu_notifier(config: ProcessingConfig = None, webhook_url: str = None) -> Optional[FeishuNotifier]:
    """
    创建飞书通知器实例
    
    Args:
        config: 处理配置
        webhook_url: webhook地址
        
    Returns:
        飞书通知器实例，如果配置无效则返回None
    """
    try:
        # 优先使用传入的webhook_url
        if webhook_url:
            return FeishuNotifier(webhook_url)
        
        # 从配置中获取webhook_url
        if config and hasattr(config, 'feishu_webhook_url') and config.feishu_webhook_url:
            return FeishuNotifier(config.feishu_webhook_url)
        
        # 使用默认webhook_url
        return FeishuNotifier()
        
    except Exception as e:
        logger.error(f"创建飞书通知器失败: {str(e)}")
        return None
