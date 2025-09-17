"""
飞书API客户端
"""
import time
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
import requests
from drama_processor.models.feishu import (
    FeishuConfig, 
    FeishuSearchResponse, 
    FeishuTokenResponse
)

logger = logging.getLogger(__name__)


def _convert_date_format(date_str: str) -> str:
    """
    将简化日期格式转换为飞书标准日期格式
    
    Args:
        date_str: 简化日期格式，如 "9.5"
        
    Returns:
        飞书标准日期格式，如 "2025-09-05"
    """
    try:
        # 当前年份
        current_year = datetime.now().year
        
        # 分割月份和日期
        if '.' in date_str:
            month_str, day_str = date_str.split('.', 1)
        else:
            raise ValueError(f"日期格式不正确，期望格式如 '9.5'，实际: {date_str}")
        
        # 转换为整数并格式化
        month = int(month_str)
        day = int(day_str)
        
        if month < 1 or month > 12:
            raise ValueError(f"月份超出范围 1-12: {month}")
        if day < 1 or day > 31:
            raise ValueError(f"日期超出范围 1-31: {day}")
        
        # 格式化为标准日期格式
        return f"{current_year}-{month:02d}-{day:02d}"
        
    except ValueError as e:
        raise ValueError(f"日期格式转换失败: {e}")
    except Exception as e:
        raise ValueError(f"日期格式转换失败: {e}")


class FeishuAPIError(Exception):
    """飞书API异常"""
    pass


class FeishuClient:
    """飞书API客户端"""
    
    def __init__(self, config: FeishuConfig):
        self.config = config
        self._access_token: Optional[str] = None
        self._token_expire_time: Optional[int] = None
        
    def _is_token_expired(self) -> bool:
        """检查token是否过期"""
        if not self._access_token or not self._token_expire_time:
            return True
        return time.time() >= self._token_expire_time
    
    def _refresh_token(self) -> None:
        """刷新访问token"""
        url = "https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal"
        
        payload = {
            "app_id": self.config.app_id,
            "app_secret": self.config.app_secret
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        try:
            logger.info("正在刷新飞书access token...")
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            
            token_response = FeishuTokenResponse(**response.json())
            
            if token_response.code != 0:
                raise FeishuAPIError(f"刷新token失败: {token_response.msg}")
            
            self._access_token = token_response.tenant_access_token
            # 设置过期时间，提前5分钟刷新
            self._token_expire_time = time.time() + (token_response.expire or 7200) - 300
            
            logger.info("飞书access token刷新成功")
            
        except requests.RequestException as e:
            raise FeishuAPIError(f"刷新token网络请求失败: {str(e)}")
        except Exception as e:
            raise FeishuAPIError(f"刷新token失败: {str(e)}")
    
    def _ensure_valid_token(self) -> None:
        """确保token有效"""
        if self._is_token_expired():
            self._refresh_token()
    
    def search_records(
        self, 
        status_filter: str = "待剪辑",
        date_filter: Optional[str] = None,
        field_names: Optional[List[str]] = None,
        page_size: Optional[int] = None,
        sort_field: str = "日期",
        sort_desc: bool = False
    ) -> FeishuSearchResponse:
        """
        搜索记录
        
        Args:
            status_filter: 状态过滤条件
            date_filter: 日期过滤条件，格式如 "2025-09-05"
            field_names: 需要获取的字段名列表
            page_size: 分页大小
            sort_field: 排序字段
            sort_desc: 是否降序
            
        Returns:
            搜索结果
        """
        self._ensure_valid_token()
        
        # 构建请求URL
        url = f"{self.config.base_url}/apps/{self.config.app_token}/tables/{self.config.table_id}/records/search"
        
        # 构建请求头
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json"
        }
        
        # 构建过滤条件
        conditions = [
            {
                "field_name": self.config.status_field_name,
                "operator": "is",
                "value": [status_filter]
            }
        ]
        
        # 如果有日期过滤条件，添加日期过滤
        if date_filter:
            # 将日期转换为时间戳（毫秒）
            try:
                # 解析日期字符串 (格式: 2025-09-05)
                date_obj = datetime.strptime(date_filter, "%Y-%m-%d")
                # 转换为毫秒时间戳
                timestamp = int(date_obj.timestamp() * 1000)
                
                conditions.append({
                    "field_name": "日期",
                    "operator": "is",
                    "value": ["ExactDate", str(timestamp)]
                })
            except ValueError as e:
                logger.warning(f"日期格式解析失败: {date_filter}, 错误: {e}")
                # 如果解析失败，仍然尝试原格式
                conditions.append({
                    "field_name": "日期",
                    "operator": "is",
                    "value": [date_filter]
                })
        
        # 构建请求体
        payload = {
            "field_names": field_names or self.config.field_names or ["剧名", "日期"],
            "page_size": page_size or self.config.page_size,
            "filter": {
                "conjunction": "and",
                "conditions": conditions
            },
            "sort": [
                {
                    "field_name": sort_field,
                    "desc": sort_desc
                }
            ]
        }
        
        try:
            if date_filter:
                logger.info(f"正在搜索飞书记录，状态过滤: {status_filter}，日期过滤: {date_filter}")
            else:
                logger.info(f"正在搜索飞书记录，状态过滤: {status_filter}")
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            
            search_response = FeishuSearchResponse(**response.json())
            
            if search_response.code != 0:
                # 特殊处理：如果是因为没有找到记录，返回空结果而不是抛出异常
                if search_response.code == 1254018:
                    logger.info("未找到符合条件的记录")
                    # 创建一个空的响应
                    empty_response = FeishuSearchResponse(code=0, msg="success", data={"items": []})
                    return empty_response
                else:
                    raise FeishuAPIError(f"搜索记录失败: {search_response.msg} (错误码: {search_response.code})")
            
            logger.info(f"成功获取 {len(search_response.items)} 条记录")
            return search_response
            
        except requests.RequestException as e:
            raise FeishuAPIError(f"搜索记录网络请求失败: {str(e)}")
        except Exception as e:
            raise FeishuAPIError(f"搜索记录失败: {str(e)}")
    
    def get_pending_dramas(self, status_filter: str = "待剪辑", date_filter: Optional[str] = None) -> List[str]:
        """
        获取指定状态的剧名列表
        
        Args:
            status_filter: 状态过滤条件（默认：待剪辑）
            date_filter: 日期过滤条件，格式如 "2025-09-05"
        
        Returns:
            剧名列表
        """
        try:
            response = self.search_records(status_filter=status_filter, date_filter=date_filter)
            return response.drama_names
        except Exception as e:
            logger.error(f"获取{status_filter}剧名失败: {str(e)}")
            raise
    
    def get_pending_dramas_with_records(self, status_filter: str = "待剪辑", date_filter: Optional[str] = None) -> Dict[str, str]:
        """
        获取指定状态的剧名和对应的记录ID
        
        Args:
            status_filter: 状态过滤条件（默认：待剪辑）
            date_filter: 日期过滤条件，格式如 "2025-09-05"
        
        Returns:
            剧名到记录ID的映射字典
        """
        try:
            response = self.search_records(status_filter=status_filter, date_filter=date_filter)
            drama_records = {}
            for record in response.items:
                if "剧名" in record.fields and record.fields["剧名"]:
                    drama_name = record.fields["剧名"][0].text
                    drama_records[drama_name] = record.record_id
            return drama_records
        except Exception as e:
            logger.error(f"获取{status_filter}剧名和记录ID失败: {str(e)}")
            raise
    
    def get_pending_dramas_with_dates(self, status_filter: str = "待剪辑", date_filter: Optional[str] = None) -> Dict[str, Dict[str, str]]:
        """
        获取指定状态的剧名和对应的记录信息（包括日期）
        
        Args:
            status_filter: 状态过滤条件（默认：待剪辑）
            date_filter: 日期过滤条件，格式如 "2025-09-05"
        
        Returns:
            剧名到记录信息的映射字典，每个记录包含 {"record_id": str, "date": str}
        """
        try:
            response = self.search_records(status_filter=status_filter, date_filter=date_filter, 
                                         field_names=["剧名", "日期"])
            drama_info = {}
            for record in response.items:
                if "剧名" in record.fields and record.fields["剧名"]:
                    drama_name = record.fields["剧名"][0].text
                    
                    # 获取日期信息
                    drama_date = None
                    if "日期" in record.fields and record.fields["日期"]:
                        # 飞书日期字段可能是时间戳格式，需要转换
                        date_value = record.fields["日期"][0].text
                        try:
                            # 尝试解析时间戳（毫秒）
                            if date_value.isdigit():
                                timestamp = int(date_value) / 1000  # 转换为秒
                                date_obj = datetime.fromtimestamp(timestamp)
                                drama_date = f"{date_obj.month}.{date_obj.day}"
                            else:
                                # 如果是日期字符串格式，尝试解析
                                if "-" in date_value:
                                    # 格式: 2025-09-06
                                    date_obj = datetime.strptime(date_value, "%Y-%m-%d")
                                    drama_date = f"{date_obj.month}.{date_obj.day}"
                                else:
                                    # 可能已经是简化格式
                                    drama_date = date_value
                        except (ValueError, TypeError) as e:
                            logger.warning(f"无法解析剧目 '{drama_name}' 的日期 '{date_value}': {e}")
                            drama_date = date_value  # 使用原始值
                    
                    drama_info[drama_name] = {
                        "record_id": record.record_id,
                        "date": drama_date or "未知"
                    }
            return drama_info
        except Exception as e:
            logger.error(f"获取{status_filter}剧名和日期信息失败: {str(e)}")
            raise
    
    def update_record_status(
        self, 
        record_id: str, 
        status: str = "待上传"
    ) -> bool:
        """
        更新记录状态
        
        Args:
            record_id: 记录ID
            status: 新状态
            
        Returns:
            是否更新成功
        """
        self._ensure_valid_token()
        
        # 使用PUT方法更新记录
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{self.config.app_token}/tables/{self.config.table_id}/records/{record_id}"
        
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "fields": {
                "当前状态": status
            }
        }
        
        try:
            logger.info(f"正在更新记录 {record_id} 状态为: {status}")
            response = requests.put(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            if result.get("code") != 0:
                raise FeishuAPIError(f"更新状态失败: {result.get('msg')}")
            
            logger.info(f"记录 {record_id} 状态更新成功")
            return True
            
        except requests.RequestException as e:
            logger.error(f"更新记录状态网络请求失败: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"更新记录状态失败: {str(e)}")
            return False
