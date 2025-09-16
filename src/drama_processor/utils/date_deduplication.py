"""基于日期的剧集去重管理器"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple

logger = logging.getLogger(__name__)


class DateDeduplicationManager:
    """基于日期的剧集去重管理器
    
    功能：
    - 记录每个日期已经处理过的剧集
    - 在拉取飞书数据时过滤已处理的剧集
    - 支持强制重新处理选项
    """
    
    def __init__(self, base_dir: Optional[Path] = None):
        """初始化日期去重管理器
        
        Args:
            base_dir: 存储目录，默认为项目根目录下的 history/date_dedup/
        """
        if base_dir is None:
            # 查找项目根目录
            current = Path.cwd()
            while current != current.parent:
                if (current / "pyproject.toml").exists():
                    base_dir = current / "history" / "date_dedup"
                    break
                current = current.parent
            else:
                base_dir = Path.cwd() / "history" / "date_dedup"
        
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        logger.debug(f"日期去重管理器初始化，存储目录: {self.base_dir}")
    
    def _get_date_file(self, date_str: str) -> Path:
        """获取日期对应的存储文件路径
        
        Args:
            date_str: 日期字符串，如 "9.12"
            
        Returns:
            存储文件路径
        """
        # 标准化日期格式：将 "9.12" 转换为 "09-12"
        normalized_date = self._normalize_date_str(date_str)
        return self.base_dir / f"{normalized_date}.json"
    
    def _normalize_date_str(self, date_str: str) -> str:
        """标准化日期字符串格式
        
        Args:
            date_str: 原始日期字符串，如 "9.12", "09.12", "9-12" 等
            
        Returns:
            标准化格式 "09-12"
        """
        # 处理各种可能的输入格式
        if '.' in date_str:
            parts = date_str.split('.')
        elif '-' in date_str:
            parts = date_str.split('-')
        else:
            # 如果没有分隔符，假设是月日格式（需要至少2位数字）
            if len(date_str) >= 2:
                parts = [date_str[:-2], date_str[-2:]]
            else:
                logger.warning(f"无法解析日期格式: {date_str}")
                return date_str.replace('.', '-')
        
        if len(parts) == 2:
            month, day = parts
            try:
                # 确保月日都是两位数
                month_int = int(month)
                day_int = int(day)
                return f"{month_int:02d}-{day_int:02d}"
            except ValueError:
                logger.warning(f"日期格式无效: {date_str}")
                return date_str.replace('.', '-')
        
        logger.warning(f"日期格式无法识别: {date_str}")
        return date_str.replace('.', '-')
    
    def load_processed_dramas(self, date_str: str) -> Set[str]:
        """加载指定日期已处理的剧集列表
        
        Args:
            date_str: 日期字符串，如 "9.12"
            
        Returns:
            已处理的剧集名称集合
        """
        date_file = self._get_date_file(date_str)
        
        if not date_file.exists():
            logger.debug(f"日期 {date_str} 无历史处理记录")
            return set()
        
        try:
            with open(date_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            processed_dramas = set(data.get('processed_dramas', []))
            logger.info(f"📅 日期 {date_str}: 加载了 {len(processed_dramas)} 个已处理剧集")
            return processed_dramas
            
        except Exception as e:
            logger.error(f"加载日期 {date_str} 的处理记录失败: {e}")
            return set()
    
    def save_processed_dramas(self, date_str: str, drama_names: List[str]):
        """保存指定日期的已处理剧集列表
        
        Args:
            date_str: 日期字符串，如 "9.12"
            drama_names: 新处理的剧集名称列表
        """
        if not drama_names:
            logger.debug(f"日期 {date_str} 无新处理剧集，跳过保存")
            return
        
        # 加载现有记录
        existing_dramas = self.load_processed_dramas(date_str)
        
        # 合并新旧记录
        all_dramas = existing_dramas.union(set(drama_names))
        
        # 准备保存数据
        data = {
            'date': date_str,
            'normalized_date': self._normalize_date_str(date_str),
            'last_updated': datetime.now().isoformat(),
            'processed_dramas': sorted(list(all_dramas)),
            'total_count': len(all_dramas)
        }
        
        # 保存到文件
        date_file = self._get_date_file(date_str)
        try:
            with open(date_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            new_count = len(set(drama_names) - existing_dramas)
            logger.info(f"💾 日期 {date_str}: 保存了 {new_count} 个新处理剧集（总计 {len(all_dramas)} 个）")
            
        except Exception as e:
            logger.error(f"保存日期 {date_str} 的处理记录失败: {e}")
    
    def filter_new_dramas(self, drama_info: Dict[str, Dict[str, str]], 
                         force_reprocess: bool = False) -> Tuple[Dict[str, Dict[str, str]], List[str]]:
        """过滤出未处理的剧集
        
        Args:
            drama_info: 剧集信息字典，格式为 {剧名: {"record_id": "xxx", "date": "9.12"}}
            force_reprocess: 是否强制重新处理（忽略历史记录）
            
        Returns:
            (过滤后的剧集信息, 被跳过的剧集列表)
        """
        if force_reprocess:
            logger.info("🔄 强制重新处理模式，跳过去重检查")
            return drama_info, []
        
        if not drama_info:
            return {}, []
        
        # 按日期分组处理
        date_groups = {}
        for drama_name, info in drama_info.items():
            date_str = info.get('date', '未知')
            if date_str not in date_groups:
                date_groups[date_str] = {}
            date_groups[date_str][drama_name] = info
        
        filtered_dramas = {}
        skipped_dramas = []
        
        for date_str, dramas_for_date in date_groups.items():
            if date_str == '未知':
                # 对于未知日期的剧集，不进行去重
                logger.warning(f"发现 {len(dramas_for_date)} 个未知日期的剧集，跳过去重")
                filtered_dramas.update(dramas_for_date)
                continue
            
            # 加载该日期已处理的剧集
            processed_dramas = self.load_processed_dramas(date_str)
            
            # 过滤该日期的剧集
            for drama_name, info in dramas_for_date.items():
                if drama_name in processed_dramas:
                    skipped_dramas.append(drama_name)
                    logger.info(f"⏭️  跳过已处理剧集: {drama_name} (日期: {date_str})")
                else:
                    filtered_dramas[drama_name] = info
                    logger.debug(f"✅ 新剧集待处理: {drama_name} (日期: {date_str})")
        
        # 统计信息
        original_count = len(drama_info)
        filtered_count = len(filtered_dramas)
        skipped_count = len(skipped_dramas)
        
        if skipped_count > 0:
            logger.info(f"📊 去重结果: 原始 {original_count} 部 -> 过滤后 {filtered_count} 部 (跳过 {skipped_count} 部)")
        else:
            logger.info(f"📊 去重结果: {original_count} 部剧集均为新剧集")
        
        return filtered_dramas, skipped_dramas
    
    def mark_dramas_as_processed(self, drama_results: List[Dict[str, any]]):
        """将成功处理的剧集标记为已处理
        
        Args:
            drama_results: 剧集处理结果列表，每个包含 {name, date, status, completed, planned} 等
        """
        # 按日期分组
        date_groups = {}
        for result in drama_results:
            drama_name = result.get('name')
            date_str = result.get('date', '未知')
            
            # 只标记完成的剧集
            completed = result.get('completed', 0)
            planned = result.get('planned', 0)
            
            if completed > 0:  # 至少完成了一些素材
                if date_str not in date_groups:
                    date_groups[date_str] = []
                date_groups[date_str].append(drama_name)
                logger.debug(f"标记剧集为已处理: {drama_name} (日期: {date_str}, 完成: {completed}/{planned})")
        
        # 保存各日期的处理记录
        for date_str, drama_names in date_groups.items():
            if date_str != '未知':
                self.save_processed_dramas(date_str, drama_names)
    
    def get_date_summary(self, date_str: str) -> Optional[Dict[str, any]]:
        """获取指定日期的处理摘要
        
        Args:
            date_str: 日期字符串，如 "9.12"
            
        Returns:
            处理摘要信息，如果没有记录返回 None
        """
        date_file = self._get_date_file(date_str)
        
        if not date_file.exists():
            return None
        
        try:
            with open(date_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            return {
                'date': data.get('date'),
                'processed_count': data.get('total_count', 0),
                'last_updated': data.get('last_updated'),
                'processed_dramas': data.get('processed_dramas', [])
            }
            
        except Exception as e:
            logger.error(f"读取日期 {date_str} 摘要失败: {e}")
            return None
    
    def list_all_processed_dates(self) -> List[Dict[str, any]]:
        """列出所有有处理记录的日期
        
        Returns:
            日期摘要列表，按日期排序
        """
        summaries = []
        
        for date_file in self.base_dir.glob("*.json"):
            try:
                with open(date_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                summaries.append({
                    'date': data.get('date'),
                    'normalized_date': data.get('normalized_date'),
                    'processed_count': data.get('total_count', 0),
                    'last_updated': data.get('last_updated'),
                    'file_path': str(date_file)
                })
                
            except Exception as e:
                logger.warning(f"读取文件失败 {date_file}: {e}")
        
        # 按标准化日期排序
        summaries.sort(key=lambda x: x.get('normalized_date', ''))
        return summaries
    
    def clear_date_record(self, date_str: str) -> bool:
        """清除指定日期的处理记录
        
        Args:
            date_str: 日期字符串，如 "9.12"
            
        Returns:
            是否成功清除
        """
        date_file = self._get_date_file(date_str)
        
        if not date_file.exists():
            logger.warning(f"日期 {date_str} 无处理记录，无需清除")
            return False
        
        try:
            date_file.unlink()
            logger.info(f"🗑️  已清除日期 {date_str} 的处理记录")
            return True
            
        except Exception as e:
            logger.error(f"清除日期 {date_str} 记录失败: {e}")
            return False


# 全局实例（单例模式）
_date_dedup_manager = None


def get_date_dedup_manager() -> DateDeduplicationManager:
    """获取全局日期去重管理器实例"""
    global _date_dedup_manager
    if _date_dedup_manager is None:
        _date_dedup_manager = DateDeduplicationManager()
    return _date_dedup_manager


