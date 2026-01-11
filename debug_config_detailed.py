#!/usr/bin/env python3
"""详细的配置加载诊断"""
import yaml
from pathlib import Path
import sys

sys.path.insert(0, 'src')

print("=" * 60)
print("Step 1: 直接读取 YAML 文件")
print("=" * 60)

# 读取主配置
with open("configs/windows_default.yaml", 'r', encoding='utf-8') as f:
    main_config = yaml.safe_load(f)

print(f"主配置 active_user: {main_config.get('active_user')}")
print(f"主配置 feishu: {main_config.get('feishu')}")
print(f"主配置 enable_feishu_features: {main_config.get('enable_feishu_features')}")

# 读取用户配置
active_user = main_config.get('active_user')
if active_user:
    user_config_path = f"configs/users/{active_user}.yaml"
    print(f"\n读取用户配置: {user_config_path}")
    try:
        with open(user_config_path, 'r', encoding='utf-8') as f:
            user_config = yaml.safe_load(f)
        print(f"用户配置 feishu: {user_config.get('feishu')}")
        print(f"用户配置 enable_feishu_features: {user_config.get('enable_feishu_features')}")
        if user_config.get('feishu'):
            print(f"  app_id: {user_config['feishu'].get('app_id')}")
            print(f"  table_id: {user_config['feishu'].get('table_id')}")
    except Exception as e:
        print(f"❌ 读取用户配置失败: {e}")

print("\n" + "=" * 60)
print("Step 2: 手动合并配置")
print("=" * 60)

def deep_update(base, override):
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_update(result[key], value)
        else:
            result[key] = value
    return result

if active_user and user_config:
    merged_config = deep_update(main_config, user_config)
    print(f"合并后 feishu: {merged_config.get('feishu')}")
    print(f"合并后 enable_feishu_features: {merged_config.get('enable_feishu_features')}")
    if merged_config.get('feishu'):
        print(f"  app_id: {merged_config['feishu'].get('app_id')}")
        print(f"  table_id: {merged_config['feishu'].get('table_id')}")

print("\n" + "=" * 60)
print("Step 3: 使用 ConfigManager 加载")
print("=" * 60)

from drama_processor.config import ConfigManager

config_path = Path("configs/windows_default.yaml")
manager = ConfigManager(config_path)
config = manager.load()

print(f"ConfigManager 加载:")
print(f"  active_user: {config.active_user}")
print(f"  enable_feishu_features: {config.enable_feishu_features}")
print(f"  feishu 是否为 None: {config.feishu is None}")
if config.feishu:
    print(f"  feishu.app_id: {config.feishu.app_id}")
    print(f"  feishu.table_id: {config.feishu.table_id}")
else:
    print("  ❌ feishu 配置为 None！")

print("=" * 60)
