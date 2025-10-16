#!/bin/bash

# 飞书剧列表剪辑快捷启动脚本
# 使用方法:
#   ./feishu_quick.sh              # 自动处理所有待处理状态的剧目
#   ./feishu_quick.sh select       # 交互式选择特定剧目
#   ./feishu_quick.sh list         # 仅查看待处理列表

set -e  # 遇到错误立即退出

# 项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 显示帮助信息
show_help() {
    echo -e "${BLUE}飞书剧列表剪辑快捷启动脚本${NC}"
    echo ""
    echo "使用方法:"
    echo "  $0 [命令] [选项]"
    echo ""
    echo "命令:"
    echo "  run     (默认) 自动处理所有待处理状态的剧目"
    echo "  select  交互式选择特定剧目进行处理"
    echo "  list    仅查看飞书表格中的待处理列表"
    echo ""
    echo "常用选项:"
    echo "  --fast        快速模式（关闭色彩扰动）"
    echo "  --jobs N      并发数（默认1，建议2-4）"
    echo "  --count N     每剧生成素材数（默认10）"
    echo "  --status S    筛选状态（默认使用配置文件中的值）"
    echo "  --help        显示帮助信息"
    echo ""
    echo "示例:"
    echo "  $0                           # 自动处理所有待处理剧目"
    echo "  $0 select --fast --jobs 4    # 快速模式选择剧目，4并发"
    echo "  $0 list --status 剪辑中      # 查看'剪辑中'状态的剧目"
    echo "  $0 select                     # 预览待处理剧目（使用默认状态）"
}

# 检查是否安装了drama-processor
check_installation() {
    if ! command -v drama-processor &> /dev/null; then
        echo -e "${RED}❌ drama-processor 未安装或未在PATH中${NC}"
        echo -e "${YELLOW}请先安装: pip install -e .${NC}"
        exit 1
    fi
}

# 解析命令行参数
COMMAND="run"
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
    case $1 in
        run|select|list)
            COMMAND="$1"
            shift
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        --fast)
            EXTRA_ARGS+=("--fast-mode")
            shift
            ;;
        --jobs)
            EXTRA_ARGS+=("--jobs" "$2")
            shift 2
            ;;
        --count)
            EXTRA_ARGS+=("--count" "$2")
            shift 2
            ;;
        --status)
            EXTRA_ARGS+=("--status" "$2")
            shift 2
            ;;
        *)
            # 其他参数直接传递
            EXTRA_ARGS+=("$1")
            shift
            ;;
    esac
done

# 检查安装
check_installation

# 显示启动信息
echo -e "${GREEN}🚀 启动飞书剧列表剪辑工具${NC}"
echo -e "${BLUE}命令: feishu $COMMAND${NC}"
if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
    echo -e "${BLUE}参数: ${EXTRA_ARGS[*]}${NC}"
fi
echo ""


# 执行命令
echo -e "${GREEN}执行命令...${NC}"
echo "drama-processor feishu $COMMAND ${EXTRA_ARGS[*]}"
echo ""

# 使用caffeinate防止系统休眠（如果可用）
if command -v caffeinate &> /dev/null && [[ "$COMMAND" != "list" ]]; then
    echo -e "${YELLOW}🔋 使用 caffeinate 防止系统休眠${NC}"
    caffeinate -i drama-processor feishu "$COMMAND" "${EXTRA_ARGS[@]}"
else
    drama-processor feishu "$COMMAND" "${EXTRA_ARGS[@]}"
fi

# 显示完成信息
echo ""
echo -e "${GREEN}✅ 飞书剧列表处理完成${NC}"
