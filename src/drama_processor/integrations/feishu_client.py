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
        # 当前日期
        now = datetime.now()
        current_year = now.year
        current_month = now.month
        
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
        
        # 跨年判断：先按当前年份解析，如果日期在过去超过180天（约6个月），则认为是明年
        # 例如：当前12月30日，目标1.1 -> 2025-01-01是364天前，超过180天 -> 明年1.1
        # 例如：当前10月1日，目标9.30 -> 2025-09-30是1天前，不超过180天 -> 今年9.30
        year = current_year
        try:
            temp_date = datetime(year, month, day).date()
            days_diff = (now.date() - temp_date).days
            # 如果日期在过去超过180天，认为是明年的日期
            if days_diff > 180:
                year = current_year + 1
        except ValueError:
            # 日期无效（如2月30日），保持当前年份
            pass
        
        # 格式化为标准日期格式
        return f"{year}-{month:02d}-{day:02d}"
        
    except ValueError as e:
        raise ValueError(f"日期格式转换失败: {e}")
    except Exception as e:
        raise ValueError(f"日期格式转换失败: {e}")


class FeishuAPIError(Exception):
    """飞书API异常"""
    pass


class FeishuRecordNotFoundError(Exception):
    """飞书记录未找到异常，用于中断剪辑"""
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
        status_filter: Optional[str] = None,
        date_filter: Optional[str] = None,
        subject_filter: Optional[str] = None,
        field_names: Optional[List[str]] = None,
        page_size: Optional[int] = None,
        sort_field: str = "日期",
        sort_desc: bool = False
    ) -> FeishuSearchResponse:
        """
        搜索记录
        
        Args:
            status_filter: 状态过滤条件，如果为None则使用配置中的默认值
            date_filter: 日期过滤条件，格式如 "2025-09-05"
            subject_filter: 主体过滤条件，如 "大号"
            field_names: 需要获取的字段名列表
            page_size: 分页大小
            sort_field: 排序字段
            sort_desc: 是否降序
            
        Returns:
            搜索结果
        """
        self._ensure_valid_token()
        
        # 使用配置中的默认状态值
        if status_filter is None:
            status_filter = self.config.pending_status_value
        
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
        
        # 如果有主体过滤条件，添加主体过滤
        if subject_filter:
            conditions.append({
                "field_name": "主体",
                "operator": "is",
                "value": [subject_filter]
            })
        
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
            filter_info = f"状态过滤: {status_filter}"
            if subject_filter:
                filter_info += f"，主体过滤: {subject_filter}"
            if date_filter:
                filter_info += f"，日期过滤: {date_filter}"
            logger.info(f"正在搜索飞书记录，{filter_info}")
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
    
    def get_pending_dramas(self, status_filter: Optional[str] = None, date_filter: Optional[str] = None, subject_filter: Optional[str] = None) -> List[str]:
        """
        获取指定状态的剧名列表
        
        Args:
            status_filter: 状态过滤条件，如果为None则使用配置中的默认值
            date_filter: 日期过滤条件，格式如 "2025-09-05"
            subject_filter: 主体过滤条件，如 "大号"
        
        Returns:
            剧名列表
        """
        try:
            response = self.search_records(status_filter=status_filter, date_filter=date_filter, subject_filter=subject_filter)
            return response.drama_names
        except Exception as e:
            actual_status = status_filter or self.config.pending_status_value
            logger.error(f"获取{actual_status}剧名失败: {str(e)}")
            raise
    
    def get_pending_dramas_with_records(self, status_filter: Optional[str] = None, date_filter: Optional[str] = None, subject_filter: Optional[str] = None) -> Dict[str, str]:
        """
        获取指定状态的剧名和对应的记录ID
        
        Args:
            status_filter: 状态过滤条件，如果为None则使用配置中的默认值
            date_filter: 日期过滤条件，格式如 "2025-09-05"
            subject_filter: 主体过滤条件，如 "大号"
        
        Returns:
            剧名到记录ID的映射字典
        """
        try:
            response = self.search_records(status_filter=status_filter, date_filter=date_filter, subject_filter=subject_filter)
            drama_records = {}
            for record in response.items:
                if "剧名" in record.fields and record.fields["剧名"]:
                    drama_name = record.fields["剧名"][0].text
                    drama_records[drama_name] = record.record_id
            return drama_records
        except Exception as e:
            actual_status = status_filter or self.config.pending_status_value
            logger.error(f"获取{actual_status}剧名和记录ID失败: {str(e)}")
            raise
    
    def get_pending_dramas_with_dates(self, status_filter: Optional[str] = None, date_filter: Optional[str] = None, subject_filter: Optional[str] = None, include_rating: bool = True) -> Dict[str, Dict[str, str]]:
        """
        获取指定状态的剧名和对应的记录信息（包括日期、上架时间、评级和抖音素材配置）
        
        Args:
            status_filter: 状态过滤条件，如果为None则使用配置中的默认值
            date_filter: 日期过滤条件，格式如 "2025-09-05"
            subject_filter: 主体过滤条件，如 "大号"
            include_rating: 是否包含评级字段（默认为True）
        
        Returns:
            剧名到记录信息的映射字典，每个记录包含：
            {
                "record_id": str,
                "date": str,          # 简化格式，如 "12.30"（用于文件命名）
                "full_date": str,     # 完整格式，如 "2025-12-30"（用于日期匹配）
                "upload_time": int,   # 上架时间戳（毫秒）
                "rating": str,        # 评级，如 "红标"（如果 include_rating=True）
                "douyin_config": str  # 抖音素材配置文本
            }
        """
        try:
            # 构建查询字段列表
            field_names = ["剧名", "日期", "上架时间"]
            
            # 只有启用评级功能时才查询评级字段
            rating_field = None
            if include_rating:
                rating_field = self.config.rating_field_name or "评级"
                field_names.append(rating_field)
            
            # 添加抖音素材字段
            douyin_field = getattr(self.config, "douyin_material_field_name", "抖音素材")
            field_names.append(douyin_field)
            highlight_field = getattr(self.config, "highlight_start_field_name", "高光起始点")
            field_names.append(highlight_field)
            
            logger.info(f"📋 查询飞书字段列表: {', '.join(field_names)}")
            
            response = self.search_records(status_filter=status_filter, date_filter=date_filter, 
                                         subject_filter=subject_filter, field_names=field_names)
            drama_info = {}
            for record in response.items:
                if "剧名" in record.fields and record.fields["剧名"]:
                    drama_name = record.fields["剧名"][0].text
                    logger.debug(f"记录字段列表: {', '.join(record.fields.keys())}")
                    
                    # 获取日期信息（同时保存完整日期和简化格式）
                    drama_date = None  # 简化格式，用于文件命名
                    full_date = None   # 完整格式，用于日期匹配
                    if "日期" in record.fields and record.fields["日期"]:
                        # 飞书日期字段可能是时间戳格式，需要转换
                        date_value = record.fields["日期"][0].text
                        try:
                            # 尝试解析时间戳（毫秒）
                            if date_value.isdigit():
                                timestamp = int(date_value) / 1000  # 转换为秒
                                date_obj = datetime.fromtimestamp(timestamp)
                                drama_date = f"{date_obj.month}.{date_obj.day}"
                                full_date = f"{date_obj.year}-{date_obj.month:02d}-{date_obj.day:02d}"
                            else:
                                # 如果是日期字符串格式，尝试解析
                                if "-" in date_value:
                                    # 格式: 2025-09-06
                                    date_obj = datetime.strptime(date_value, "%Y-%m-%d")
                                    drama_date = f"{date_obj.month}.{date_obj.day}"
                                    full_date = date_value
                                else:
                                    # 可能已经是简化格式，尝试补全年份
                                    drama_date = date_value
                                    # 尝试解析并补全年份
                                    if "." in date_value:
                                        try:
                                            month, day = date_value.split(".", 1)
                                            current_year = datetime.now().year
                                            full_date = f"{current_year}-{int(month):02d}-{int(day):02d}"
                                        except:
                                            full_date = None
                        except (ValueError, TypeError) as e:
                            logger.warning(f"无法解析剧目 '{drama_name}' 的日期 '{date_value}': {e}")
                            drama_date = date_value  # 使用原始值
                            full_date = None
                    
                    # 获取上架时间信息
                    upload_time = None
                    if "上架时间" in record.fields and record.fields["上架时间"]:
                        try:
                            # 上架时间已被转换为 List[FeishuFieldValue]
                            upload_time_obj = record.fields["上架时间"]
                            if isinstance(upload_time_obj, list) and len(upload_time_obj) > 0:
                                first_item = upload_time_obj[0]
                                # 尝试获取 text 字段
                                time_value = None
                                if hasattr(first_item, "text"):
                                    time_value = first_item.text
                                elif isinstance(first_item, dict) and "text" in first_item:
                                    time_value = first_item["text"]
                                
                                if time_value and time_value.isdigit():
                                    upload_time = int(time_value)
                        except (ValueError, TypeError, KeyError, IndexError, AttributeError) as e:
                            logger.warning(f"无法解析剧目 '{drama_name}' 的上架时间: {e}")
                    
                    # 获取评级信息（仅在 include_rating=True 时）
                    rating = None
                    if include_rating and rating_field and rating_field in record.fields and record.fields[rating_field]:
                        try:
                            # 评级已被转换为 List[FeishuFieldValue]
                            rating_obj = record.fields[rating_field]
                            if isinstance(rating_obj, list) and len(rating_obj) > 0:
                                first_item = rating_obj[0]
                                # 尝试获取 text 字段
                                if hasattr(first_item, "text"):
                                    rating = first_item.text
                                elif isinstance(first_item, dict) and "text" in first_item:
                                    rating = first_item["text"]
                        except (KeyError, IndexError, TypeError, AttributeError) as e:
                            logger.warning(f"无法解析剧目 '{drama_name}' 的评级: {e}")
                    
                    # 获取抖音素材配置信息
                    douyin_config = None
                    if douyin_field in record.fields and record.fields[douyin_field]:
                        try:
                            # 抖音素材结构: [{"text": "小红看剧 ...\n...", "type": "text"}]
                            douyin_obj = record.fields[douyin_field]
                            if isinstance(douyin_obj, list) and len(douyin_obj) > 0:
                                # 取第一个元素的text字段
                                first_item = douyin_obj[0]
                                if isinstance(first_item, dict) and "text" in first_item:
                                    douyin_config = first_item["text"]
                                    logger.info(f"📱 获取到剧目 '{drama_name}' 的抖音素材配置")
                                elif hasattr(first_item, "text"):
                                    # 可能是对象而不是字典
                                    douyin_config = first_item.text
                                    logger.info(f"📱 获取到剧目 '{drama_name}' 的抖音素材配置")
                        except (KeyError, IndexError, TypeError, AttributeError) as e:
                            logger.warning(f"⚠️ 无法解析剧目 '{drama_name}' 的抖音素材配置: {e}")
                    else:
                        logger.debug(f"剧目 '{drama_name}' 没有抖音素材配置字段（字段名: {douyin_field}）")

                    # 获取高光起始点字段
                    highlight_start_points = None
                    if highlight_field in record.fields and record.fields[highlight_field]:
                        try:
                            highlight_obj = record.fields[highlight_field]
                            if isinstance(highlight_obj, list) and len(highlight_obj) > 0:
                                lines = []
                                for field_item in highlight_obj:
                                    if isinstance(field_item, dict) and "text" in field_item:
                                        text = str(field_item["text"]).strip()
                                    elif hasattr(field_item, "text"):
                                        text = str(field_item.text).strip()
                                    else:
                                        text = str(field_item).strip()
                                    if text:
                                        lines.append(text)
                                if lines:
                                    highlight_start_points = "\n".join(lines)
                        except (KeyError, IndexError, TypeError, AttributeError) as e:
                            logger.warning(f"⚠️ 无法解析剧目 '{drama_name}' 的高光起始点: {e}")
                    
                    drama_info[drama_name] = {
                        "record_id": record.record_id,
                        "date": drama_date or "未知",           # 简化格式，用于文件命名
                        "full_date": full_date,                 # 完整格式，用于日期匹配
                        "upload_time": upload_time,             # None 表示没有上架时间
                        "rating": rating,                       # None 表示没有评级
                        "douyin_config": douyin_config,         # None 表示没有抖音素材配置
                        "highlight_start_points": highlight_start_points
                    }
            return drama_info
        except Exception as e:
            actual_status = status_filter or self.config.pending_status_value
            filter_desc = f"获取{actual_status}剧名和日期信息失败"
            if subject_filter:
                filter_desc = f"获取{actual_status}且主体为{subject_filter}的剧名和日期信息失败"
            logger.error(f"{filter_desc}: {str(e)}")
            raise
    
    def update_record_status(
        self, 
        record_id: str, 
        status: str = "待上传",
        remark: str = None
    ) -> bool:
        """
        更新记录状态（可选更新备注）
        
        Args:
            record_id: 记录ID
            status: 新状态
            remark: 备注内容（可选）
            
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
        
        # 构建更新字段
        fields = {
            self.config.status_field_name: status
        }
        
        # 如果提供了备注，一并更新
        if remark is not None:
            fields[self.config.remark_field_name] = remark
        
        payload = {
            "fields": fields
        }
        
        try:
            if remark:
                logger.info(f"正在更新记录 {record_id} 状态为: {status}，备注: {remark}")
            else:
                logger.info(f"正在更新记录 {record_id} 状态为: {status}")
            response = requests.put(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            if result.get("code") != 0:
                error_msg = result.get('msg', '')
                if error_msg == 'RecordIdNotFound':
                    raise FeishuRecordNotFoundError(f"记录ID未找到，中断这部剧的剪辑: {record_id}")
                else:
                    raise FeishuAPIError(f"更新状态失败: {error_msg}")
            
            logger.info(f"记录 {record_id} 状态更新成功")
            return True
            
        except requests.RequestException as e:
            logger.error(f"更新记录状态网络请求失败: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"更新记录状态失败: {str(e)}")
            return False
