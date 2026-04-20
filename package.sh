#!/bin/bash

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

echo "========================================"
echo "   Drama Processor 通用运行时打包"
echo "========================================"
echo ""

output_dir="${1:-$HOME/Desktop/打包输出}"

if command -v pwsh >/dev/null 2>&1; then
    pwsh -NoProfile -ExecutionPolicy Bypass -Command "& {./package.ps1 -OutputDir '$output_dir'}"
elif command -v powershell >/dev/null 2>&1; then
    powershell -NoProfile -ExecutionPolicy Bypass -Command "& {./package.ps1 -OutputDir '$output_dir'}"
else
    echo -e "${RED}错误：未找到 PowerShell！${NC}"
    echo ""
    echo "请先安装 PowerShell Core:"
    echo "  brew install --cask powershell"
    echo ""
    echo "或者手动运行打包脚本："
    echo "  pwsh ./package.ps1 -OutputDir '$output_dir'"
    exit 1
fi

echo ""
echo "========================================"
echo -e "  ${GREEN}通用运行时打包完成！${NC}"
echo -e "  输出：${CYAN}$output_dir${NC}"
echo "========================================"
