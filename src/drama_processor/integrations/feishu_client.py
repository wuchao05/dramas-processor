"""
飞书API客户端
"""
import time
import logging
from typing import Optional, List, Dict, Any
import requests
from drama_processor.models.feishu import (
    FeishuConfig, 
    FeishuSearchResponse, 
    FeishuTokenResponse
)

logger = logging.getLogger(__name__)


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
        status_filter: str = "待搭建",
        field_names: Optional[List[str]] = None,
        page_size: Optional[int] = None,
        sort_field: str = "日期",
        sort_desc: bool = True
    ) -> FeishuSearchResponse:
        """
        搜索记录
        
        Args:
            status_filter: 状态过滤条件
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
        
        # 构建请求体
        payload = {
            "field_names": field_names or self.config.field_names or ["剧名", "日期"],
            "page_size": page_size or self.config.page_size,
            "filter": {
                "conjunction": "and",
                "conditions": [
                    {
                        "field_name": self.config.status_field_name,
                        "operator": "is",
                        "value": [status_filter]
                    }
                ]
            },
            "sort": [
                {
                    "field_name": sort_field,
                    "desc": sort_desc
                }
            ]
        }
        
        try:
            logger.info(f"正在搜索飞书记录，状态过滤: {status_filter}")
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            
            search_response = FeishuSearchResponse(**response.json())
            
            if search_response.code != 0:
                raise FeishuAPIError(f"搜索记录失败: {search_response.msg}")
            
            logger.info(f"成功获取 {len(search_response.items)} 条记录")
            return search_response
            
        except requests.RequestException as e:
            raise FeishuAPIError(f"搜索记录网络请求失败: {str(e)}")
        except Exception as e:
            raise FeishuAPIError(f"搜索记录失败: {str(e)}")
    
    def get_pending_dramas(self, status_filter: str = "待剪辑") -> List[str]:
        """
        获取指定状态的剧名列表
        
        Args:
            status_filter: 状态过滤条件（默认：待剪辑）
        
        Returns:
            剧名列表
        """
        try:
            response = self.search_records(status_filter=status_filter)
            return response.drama_names
        except Exception as e:
            logger.error(f"获取{status_filter}剧名失败: {str(e)}")
            raise
    
    def get_pending_dramas_with_records(self, status_filter: str = "待剪辑") -> Dict[str, str]:
        """
        获取指定状态的剧名和对应的记录ID
        
        Args:
            status_filter: 状态过滤条件（默认：待剪辑）
        
        Returns:
            剧名到记录ID的映射字典
        """
        try:
            response = self.search_records(status_filter=status_filter)
            drama_records = {}
            for record in response.items:
                if "剧名" in record.fields and record.fields["剧名"]:
                    drama_name = record.fields["剧名"][0].text
                    drama_records[drama_name] = record.record_id
            return drama_records
        except Exception as e:
            logger.error(f"获取{status_filter}剧名和记录ID失败: {str(e)}")
            raise
    
    def update_record_status(
        self, 
        record_id: str, 
        status: str = "已完成"
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
