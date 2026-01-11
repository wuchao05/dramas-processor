#!/usr/bin/env python3
"""测试配置加载"""
from pathlib import Path
import sys

# 确保能导入模块
sys.path.insert(0, 'src')

from drama_processor.config import ConfigManager

# 加载配置
config_path = Path("configs/windows_default.yaml")
manager = ConfigManager(config_path)
config = manager.load()

print("=" * 60)
print("配置加载测试")
print("=" * 60)
print(f"配置文件: {config_path}")
print(f"active_user: {config.active_user}")
print(f"enable_feishu_features: {config.enable_feishu_features}")
print(f"feishu 是否为 None: {config.feishu is None}")
if config.feishu:
    print(f"feishu.app_id: {config.feishu.app_id}")
    app_secret_display = config.feishu.app_secret[:10] + "..." if config.feishu.app_secret else "None"
    print(f"feishu.app_secret: {app_secret_display}")
    print(f"feishu.app_token: {config.feishu.app_token}")
    print(f"feishu.table_id: {config.feishu.table_id}")
else:
    print("❌ feishu 配置为空！")
print(f"default_source_dir: {config.default_source_dir}")
print("=" * 60)
