#!/bin/bash
# WSL 环境检查和设置脚本

echo "=== WSL 环境检查 ==="
echo ""

# 检查并创建临时目录
echo "1. 检查临时目录..."
TEMP_DIR="/home/drama_temp"
CACHE_DIR="/home/tails_cache"

if [ ! -d "$TEMP_DIR" ]; then
    echo "   ⚠️  临时目录不存在，正在创建: $TEMP_DIR"
    sudo mkdir -p "$TEMP_DIR"
    sudo chmod 777 "$TEMP_DIR"
    echo "   ✅ 创建成功"
else
    echo "   ✅ 临时目录已存在: $TEMP_DIR"
fi

if [ ! -d "$CACHE_DIR" ]; then
    echo "   ⚠️  缓存目录不存在，正在创建: $CACHE_DIR"
    sudo mkdir -p "$CACHE_DIR"
    sudo chmod 777 "$CACHE_DIR"
    echo "   ✅ 创建成功"
else
    echo "   ✅ 缓存目录已存在: $CACHE_DIR"
fi

# 检查权限
echo ""
echo "2. 检查目录权限..."
ls -ld "$TEMP_DIR"
ls -ld "$CACHE_DIR"

# 检查字体
echo ""
echo "3. 检查中文字体..."
FONT_PATH="/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
if [ -f "$FONT_PATH" ]; then
    echo "   ✅ 字体文件存在: $FONT_PATH"
else
    echo "   ⚠️  字体文件不存在: $FONT_PATH"
    echo "   正在安装中文字体..."
    sudo apt update
    sudo apt install -y fonts-wqy-zenhei fonts-wqy-microhei
    if [ -f "$FONT_PATH" ]; then
        echo "   ✅ 字体安装成功"
    else
        echo "   ❌ 字体安装失败，请手动安装: sudo apt install fonts-wqy-zenhei"
    fi
fi

# 检查磁盘空间
echo ""
echo "4. 检查磁盘空间..."
echo "   /tmp 分区:"
df -h /tmp | tail -1
echo "   /home 分区:"
df -h /home | tail -1
echo "   D 盘挂载点:"
df -h /mnt/d 2>/dev/null | tail -1 || echo "   ⚠️  D盘未挂载"

echo ""
echo "=== 检查完成 ==="

