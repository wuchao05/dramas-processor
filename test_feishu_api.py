#!/usr/bin/env python3
"""测试飞书 API 凭证"""
import requests
import json

print("=" * 60)
print("飞书 API 凭证测试")
print("=" * 60)

# 从配置文件读取凭证
import yaml
from pathlib import Path

config_path = Path("configs/windows_default.yaml")
with open(config_path, 'r', encoding='utf-8') as f:
    main_config = yaml.safe_load(f)

active_user = main_config.get('active_user')
user_config_path = f"configs/users/{active_user}.yaml"

with open(user_config_path, 'r', encoding='utf-8') as f:
    user_config = yaml.safe_load(f)

feishu_config = user_config.get('feishu', {})

app_id = feishu_config.get('app_id')
app_secret = feishu_config.get('app_secret')
app_token = feishu_config.get('app_token')
table_id = feishu_config.get('table_id')

print(f"\n读取到的凭证:")
print(f"  app_id: {app_id}")
print(f"  app_secret: {app_secret[:10]}...{app_secret[-10:] if app_secret else ''}")
print(f"  app_token: {app_token}")
print(f"  table_id: {table_id}")

# 测试 token 刷新
print(f"\n测试 1: 刷新 access token")
print("-" * 60)

url = "https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal"

payload = {
    "app_id": app_id,
    "app_secret": app_secret
}

headers = {
    "Content-Type": "application/json"
}

try:
    print(f"请求 URL: {url}")
    print(f"请求数据: {json.dumps(payload, indent=2)}")
    print("\n发送请求...")
    
    response = requests.post(url, json=payload, headers=headers, timeout=30)
    
    print(f"响应状态码: {response.status_code}")
    print(f"响应内容: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    
    result = response.json()
    
    if result.get('code') == 0:
        print("\n✅ Token 刷新成功！")
        access_token = result.get('tenant_access_token')
        print(f"Access Token: {access_token[:20]}...{access_token[-20:] if access_token else ''}")
        
        # 测试查询表格
        print(f"\n测试 2: 查询多维表格")
        print("-" * 60)
        
        search_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/search"
        
        search_headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        search_payload = {
            "filter": {
                "conjunction": "and",
                "conditions": [
                    {
                        "field_name": "当前状态",
                        "operator": "is",
                        "value": ["待剪辑"]
                    }
                ]
            },
            "automatic_fields": False,
            "page_size": 10
        }
        
        print(f"请求 URL: {search_url}")
        print(f"请求头: Authorization: Bearer {access_token[:20]}...")
        print("\n发送查询请求...")
        
        search_response = requests.post(search_url, json=search_payload, headers=search_headers, timeout=30)
        
        print(f"响应状态码: {search_response.status_code}")
        print(f"响应内容: {json.dumps(search_response.json(), indent=2, ensure_ascii=False)}")
        
        search_result = search_response.json()
        
        if search_result.get('code') == 0:
            print("\n✅ 查询成功！")
            items = search_result.get('data', {}).get('items', [])
            print(f"找到 {len(items)} 条待剪辑记录")
        else:
            print(f"\n❌ 查询失败: {search_result.get('msg')}")
            
    else:
        print(f"\n❌ Token 刷新失败!")
        print(f"错误代码: {result.get('code')}")
        print(f"错误信息: {result.get('msg')}")
        
        # 分析可能的原因
        print("\n可能的原因:")
        if result.get('code') == 10012 or 'invalid' in result.get('msg', '').lower():
            print("  - app_id 或 app_secret 不正确")
            print("  - 请检查飞书开放平台应用配置")
            print("  - 确认应用是否启用")
        
except requests.RequestException as e:
    print(f"\n❌ 网络请求失败: {e}")
except Exception as e:
    print(f"\n❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
