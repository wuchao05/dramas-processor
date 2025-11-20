"""
飞书API集成模型
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class FeishuConfig(BaseModel):
    """飞书API配置"""
    app_id: str = Field(..., description="飞书应用ID")
    app_secret: str = Field(..., description="飞书应用密钥")
    app_token: str = Field(..., description="飞书应用token")
    table_id: str = Field(..., description="多维表格ID")
    base_url: str = Field(default="https://open.feishu.cn/open-apis/bitable/v1", description="API基础URL")
    field_names: List[str] = Field(default_factory=list, description="需要获取的字段名")
    status_field_name: str = Field(default="当前状态", description="状态字段名")
    pending_status_value: str = Field(default="待剪辑", description="待处理状态值")
    completed_status_value: str = Field(default="已完成", description="已完成状态值")
    processing_status_value: str = Field(default="剪辑中", description="处理中状态值")
    missing_source_status_value: str = Field(default="无源视频", description="无源素材状态值")
    page_size: int = Field(default=200, description="分页大小")
    token_refresh_interval: int = Field(default=7200000, description="token刷新间隔(毫秒)")


class FeishuFieldValue(BaseModel):
    """飞书字段值"""
    text: str
    type: str = "text"


class FeishuRecord(BaseModel):
    """飞书记录"""
    record_id: str
    fields: Dict[str, List[FeishuFieldValue]]


class FeishuSearchResponse(BaseModel):
    """飞书搜索响应"""
    code: int
    msg: str
    data: Optional[Dict[str, Any]] = None
    
    @property
    def items(self) -> List[FeishuRecord]:
        """获取记录列表"""
        if self.code != 0 or self.data is None or "items" not in self.data:
            return []
        
        records = []
        for item in self.data["items"]:
            # 转换字段值格式
            fields = {}
            for field_name, field_data in item["fields"].items():
                if isinstance(field_data, list):
                    fields[field_name] = [FeishuFieldValue(**value) for value in field_data]
                else:
                    # 处理其他类型的字段值
                    fields[field_name] = [FeishuFieldValue(text=str(field_data), type="text")]
            
            records.append(FeishuRecord(
                record_id=item["record_id"],
                fields=fields
            ))
        return records
    
    @property
    def drama_names(self) -> List[str]:
        """获取剧名列表"""
        drama_names = []
        for record in self.items:
            if "剧名" in record.fields and record.fields["剧名"]:
                drama_names.append(record.fields["剧名"][0].text)
        return drama_names


class FeishuTokenResponse(BaseModel):
    """飞书token响应"""
    code: int
    msg: str
    tenant_access_token: Optional[str] = None
    expire: Optional[int] = None
