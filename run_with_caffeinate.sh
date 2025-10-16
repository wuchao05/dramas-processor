#!/bin/bash
# 防止电脑休眠的剧集处理脚本

echo "🚀 启动剧集处理器 (防止休眠模式)"
echo "=================================="

# 检查是否有参数传入
if [ $# -eq 0 ]; then
    echo "使用方法: $0 [drama-processor参数]"
    echo ""
    echo "示例:"
    echo "  $0 process --count 2 --verbose"
    echo "  $0 feishu run"
    echo "  $0 analyze /path/to/dramas"
    exit 1
fi

echo "📋 执行命令: drama-processor $*"
echo "⚡ 防止系统休眠: caffeinate -i"
echo ""

# 使用caffeinate防止系统休眠，同时运行drama-processor
# -i: 防止系统进入空闲睡眠
# -d: 防止显示器休眠 (可选)
# -s: 防止系统睡眠当AC电源断开时 (可选)

caffeinate -i drama-processor "$@"

exit_code=$?

echo ""
echo "=================================="
if [ $exit_code -eq 0 ]; then
    echo "✅ 剧集处理完成!"
else
    echo "❌ 剧集处理失败 (退出代码: $exit_code)"
fi
echo "🔋 系统休眠保护已解除"
