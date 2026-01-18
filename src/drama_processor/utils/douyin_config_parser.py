"""抖音素材配置解析器

从飞书"抖音素材"字段提取抖音号配置和素材数量。
"""

import logging
import re
from typing import Optional, Dict, List

from ..models.config import BrandTextMapping, BrandTextRange


logger = logging.getLogger(__name__)


def parse_douyin_material_config(config_text: str) -> Optional[Dict]:
    """
    解析飞书"抖音素材"字段文本
    
    Args:
        config_text: 多行文本，每行格式 "抖音号名称 抖音号ID 序号范围"
                    例如: "小红看剧 25655660267 01-05"
    
    Returns:
        {
            "brand_text_mapping": BrandTextMapping对象,
            "count": int  # 从序号范围计算出的总数
        }
        如果解析失败返回None
    
    Example:
        >>> text = "小红看剧 25655660267 01-05\\n斯娜看剧 34996393230 06-10"
        >>> result = parse_douyin_material_config(text)
        >>> result["count"]
        10
        >>> len(result["brand_text_mapping"].ranges)
        2
    """
    if not config_text or not config_text.strip():
        return None
    
    try:
        lines = config_text.strip().split('\n')
        ranges = []
        max_number = 0
        parsed_count = 0
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
            
            # 按空格分割，期望至少3个部分：名称 ID 范围
            parts = line.split()
            if len(parts) < 3:
                logger.warning(f"抖音素材配置第{line_num}行格式错误（少于3个字段）: {line}")
                continue
            
            # 提取：第一个是名称，最后一个是范围，中间的是ID（可能包含空格）
            name = parts[0]
            range_str = parts[-1]
            # ID是中间部分，可能有多个空格分隔的部分
            douyin_id = ' '.join(parts[1:-1])
            
            # 验证范围格式（支持 "01-05" 或 "01,02,03" 或 "01"）
            if not re.match(r'^\d+(-\d+|,\d+)*$', range_str):
                logger.warning(f"抖音素材配置第{line_num}行范围格式错误: {range_str}")
                continue
            
            # 计算该范围的最大序号
            try:
                range_max = _get_max_number_from_range(range_str)
                if range_max > max_number:
                    max_number = range_max
            except Exception as e:
                logger.warning(f"抖音素材配置第{line_num}行范围解析失败: {e}")
                continue
            
            # 创建 BrandTextRange 对象
            brand_range = BrandTextRange(
                range=range_str,
                text=name
            )
            ranges.append(brand_range)
            parsed_count += 1
            
            logger.debug(f"解析抖音配置: {name} (ID: {douyin_id}) -> {range_str}")
        
        if parsed_count == 0:
            logger.warning("抖音素材配置解析失败：没有有效的配置行")
            return None
        
        # 构建 BrandTextMapping
        brand_mapping = BrandTextMapping(
            mode="range",
            ranges=ranges,
            default_text=ranges[0].text if ranges else "热门短剧"  # 使用第一个作为默认值
        )
        
        result = {
            "brand_text_mapping": brand_mapping,
            "count": max_number
        }
        
        logger.info(f"✅ 抖音素材配置解析成功：{parsed_count}个抖音号，素材数量={max_number}")
        return result
        
    except Exception as e:
        logger.error(f"解析抖音素材配置时发生异常: {e}", exc_info=True)
        return None


def _get_max_number_from_range(range_str: str) -> int:
    """
    从范围字符串中提取最大序号
    
    Args:
        range_str: 范围字符串，如 "01-05", "01,02,03", "01"
    
    Returns:
        最大序号
    
    Example:
        >>> _get_max_number_from_range("01-05")
        5
        >>> _get_max_number_from_range("35-38")
        38
        >>> _get_max_number_from_range("01,02,03")
        3
    """
    numbers = []
    
    # 处理逗号分隔的数字: "01,02,03"
    if ',' in range_str:
        parts = range_str.split(',')
        for part in parts:
            try:
                numbers.append(int(part.strip()))
            except ValueError:
                pass
    
    # 处理范围: "01-05"
    elif '-' in range_str:
        try:
            start, end = range_str.split('-', 1)
            start_num = int(start.strip())
            end_num = int(end.strip())
            numbers.extend([start_num, end_num])
        except ValueError:
            pass
    
    # 处理单个数字: "01"
    else:
        try:
            numbers.append(int(range_str.strip()))
        except ValueError:
            pass
    
    if not numbers:
        raise ValueError(f"无法从范围字符串提取数字: {range_str}")
    
    return max(numbers)
