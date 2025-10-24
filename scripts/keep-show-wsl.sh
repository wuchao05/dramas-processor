#!/usr/bin/env bash
# WSL 专用启动脚本
# 自动处理剪贴板并调用主脚本

set -euo pipefail

# 获取脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAIN_SCRIPT="${SCRIPT_DIR}/keep-show.sh"

# 检查主脚本是否存在
if [[ ! -f "$MAIN_SCRIPT" ]]; then
    echo "[ERR] 找不到主脚本：$MAIN_SCRIPT" >&2
    exit 1
fi

# 检查是否有剪贴板工具
if command -v xclip >/dev/null 2>&1; then
    # 使用 xclip 读取剪贴板并传递给主脚本
    xclip -selection clipboard -o | "$MAIN_SCRIPT" "$@"
elif command -v xsel >/dev/null 2>&1; then
    # 使用 xsel 读取剪贴板并传递给主脚本
    xsel --clipboard --output | "$MAIN_SCRIPT" "$@"
elif command -v powershell.exe >/dev/null 2>&1; then
    # 使用 Windows PowerShell 读取剪贴板
    powershell.exe -Command "Get-Clipboard" | "$MAIN_SCRIPT" --wsl "$@"
else
    echo "[ERR] 没有可用的剪贴板工具" >&2
    echo "请安装以下工具之一：" >&2
    if command -v pacman >/dev/null 2>&1; then
        echo "  sudo pacman -S xclip" >&2
    elif command -v apt-get >/dev/null 2>&1; then
        echo "  sudo apt-get install xclip" >&2
    elif command -v yum >/dev/null 2>&1; then
        echo "  sudo yum install xclip" >&2
    else
        echo "  xclip 或 xsel" >&2
    fi
    echo "" >&2
    echo "或者使用管道输入：" >&2
    echo "  echo '剧名1' | ./keep-show.sh '/mnt/c/dramas'" >&2
    exit 1
fi
