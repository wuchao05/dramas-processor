#!/usr/bin/env python3
"""检查 Windows 系统中可用的中文字体"""
import os
from pathlib import Path

print("=" * 60)
print("Windows 中文字体检查")
print("=" * 60)

fonts_dir = Path("C:/Windows/Fonts")

# 检查常见中文字体
fonts_to_check = [
    ("微软雅黑 TTF", "msyh.ttf"),
    ("微软雅黑粗体 TTF", "msyhbd.ttf"),
    ("微软雅黑 TTC", "msyh.ttc"),
    ("微软雅黑粗体 TTC", "msyhbd.ttc"),
    ("黑体 TTF", "simhei.ttf"),
    ("楷体 TTF", "simkai.ttf"),
    ("宋体 TTC", "simsun.ttc"),
]

print("\n检查结果：\n")

found_fonts = []
for name, filename in fonts_to_check:
    font_path = fonts_dir / filename
    exists = font_path.exists()
    status = "✅ 存在" if exists else "❌ 不存在"
    print(f"{status}  {name:20s}  {font_path}")
    
    if exists:
        found_fonts.append((name, str(font_path)))

print("\n" + "=" * 60)
print("推荐配置：")
print("=" * 60)

if found_fonts:
    print("\n在你的配置文件中添加以下任意一个：\n")
    for i, (name, path) in enumerate(found_fonts[:3], 1):
        # 转义反斜杠
        yaml_path = path.replace("\\", "\\\\")
        print(f"# 方案 {i}：使用 {name}")
        print(f"font_file: \"{yaml_path}\"\n")
else:
    print("\n⚠️  未找到任何中文字体！请安装微软雅黑或黑体。")

print("=" * 60)
print("\n提示：")
print("- TTF 文件（单字体）最稳定，推荐优先使用")
print("- TTC 文件（字体集合）需要 fontindex，代码已自动处理")
print("- 如果都不存在，可能需要更新 Windows 字体包")
print("=" * 60)
