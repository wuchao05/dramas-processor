#!/bin/bash
# 短剧剪辑工具 - Mac 打包脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo "========================================"
echo "   短剧剪辑工具 - 打包工具 (Mac)"
echo "========================================"
echo ""

# 检查 configs/users 目录
if [ ! -d "configs/users" ]; then
    echo -e "${RED}错误：找不到 configs/users/ 目录！${NC}"
    exit 1
fi

# 扫描可用配置
echo -e "${YELLOW}正在扫描可用的达人配置...${NC}"
echo ""
echo "请选择打包对象："
echo ""

# 读取所有非 -daily 的 yaml 文件
configs=()
index=1
for file in configs/users/*.yaml; do
    filename=$(basename "$file" .yaml)
    # 排除 -daily 结尾的文件
    if [[ ! "$filename" =~ -daily$ ]]; then
        echo "[$index] $filename"
        configs+=("$filename")
        ((index++))
    fi
done

if [ ${#configs[@]} -eq 0 ]; then
    echo -e "${RED}错误：configs/users/ 目录下没有找到任何配置文件！${NC}"
    exit 1
fi

echo ""
echo "[0] 退出"
echo ""

# 读取用户选择
read -p "请输入选项 (0-${#configs[@]}): " choice

if [ "$choice" == "0" ]; then
    exit 0
fi

# 验证输入
if ! [[ "$choice" =~ ^[0-9]+$ ]] || [ "$choice" -lt 1 ] || [ "$choice" -gt ${#configs[@]} ]; then
    echo -e "${RED}无效选项！${NC}"
    exit 1
fi

# 获取选择的配置名
name="${configs[$((choice-1))]}"

echo ""
echo -e "${YELLOW}正在为 ${name} 打包...${NC}"
echo ""

# 设置输出目录
output_dir="$HOME/Desktop/打包输出"

# 调用 PowerShell 脚本
if command -v pwsh &> /dev/null; then
    # 使用 PowerShell Core
    pwsh -NoProfile -ExecutionPolicy Bypass -Command "& {./package.ps1 -Name '$name' -OutputDir '$output_dir'}"
elif command -v powershell &> /dev/null; then
    # 使用旧版 PowerShell（如果有）
    powershell -NoProfile -ExecutionPolicy Bypass -Command "& {./package.ps1 -Name '$name' -OutputDir '$output_dir'}"
else
    echo -e "${RED}错误：未找到 PowerShell！${NC}"
    echo ""
    echo "请先安装 PowerShell Core:"
    echo "  brew install --cask powershell"
    echo ""
    echo "或者手动运行打包脚本："
    echo "  pwsh ./package.ps1 -Name '$name' -OutputDir '$output_dir'"
    exit 1
fi

if [ $? -ne 0 ]; then
    echo ""
    echo -e "${RED}打包失败！请检查错误信息。${NC}"
    exit 1
fi

echo ""
echo "========================================"
echo -e "  ${GREEN}打包完成！${NC}"
echo "  配置：$name"
echo "  输出：$output_dir"
echo "========================================"
