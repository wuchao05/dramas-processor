#!/bin/bash
# AI功能快速安装脚本（简化版本）

set -e

echo "🤖 开始安装Drama Processor AI功能（简化版本）..."

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 未安装，请先安装Python3"
    exit 1
fi

# 检查pip
if ! command -v pip &> /dev/null; then
    echo "❌ pip 未安装，请先安装pip"
    exit 1
fi

echo "✅ Python环境检查通过"

# 安装简化的AI依赖
echo "📦 安装AI依赖包（简化版本）..."
pip install -r requirements_ai.txt

# 检查系统类型并安装FFmpeg（用于视频处理）
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    echo "🍎 检测到macOS系统"
    
    # 检查brew
    if command -v brew &> /dev/null; then
        echo "📦 安装FFmpeg..."
        brew install ffmpeg
    else
        echo "⚠️  Homebrew未安装，请手动安装FFmpeg"
        echo "   或访问: https://brew.sh/ 安装Homebrew"
    fi
    
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    echo "🐧 检测到Linux系统"
    
    if command -v apt-get &> /dev/null; then
        echo "📦 安装FFmpeg..."
        sudo apt-get update
        sudo apt-get install -y ffmpeg libsm6 libxext6 libxrender-dev libglib2.0-0
    elif command -v yum &> /dev/null; then
        echo "📦 安装FFmpeg..."
        sudo yum install -y ffmpeg
    else
        echo "⚠️  请手动安装FFmpeg"
    fi
    
else
    echo "⚠️  未知操作系统，请手动安装FFmpeg"
fi

echo "ℹ️  简化版本暂时不需要 Tesseract OCR 和 librosa"

# 创建模型目录
echo "📁 创建模型缓存目录..."
mkdir -p ~/.drama_processor/models
mkdir -p logs/ai

# 下载基础模型
echo "📥 初始化AI模块..."
python -c "
try:
    from src.drama_processor.ai.models.model_downloader import ModelDownloader
    downloader = ModelDownloader()
    print('✅ 模型下载器初始化成功')
except Exception as e:
    print('⚠️  模型下载器初始化失败:', e)
"

# 创建示例配置文件
echo "⚙️  检查AI配置文件..."
if [ -f "configs/ai_config.yaml" ]; then
    echo "✅ AI配置文件已存在"
else
    echo "❌ AI配置文件不存在，请确保configs/ai_config.yaml文件存在"
fi

# 验证安装
echo "🔍 验证安装..."

# 检查Python包
python -c "
try:
    import cv2
    import numpy as np
    import requests
    print('✅ 基础依赖包检查通过')
except ImportError as e:
    print('❌ 依赖包检查失败:', e)
    exit(1)
"

# 检查FFmpeg
if command -v ffmpeg &> /dev/null; then
    echo "✅ FFmpeg 安装成功"
    ffmpeg -version | head -1
else
    echo "⚠️  FFmpeg 未安装，视频处理功能可能受限"
fi

echo ""
echo "🎉 AI功能（简化版本）安装完成！"
echo ""
echo "📖 使用指南:"
echo "   1. 编辑 configs/ai_config.yaml 启用所需功能"
echo "   2. 运行: drama-processor ai analyze-scenes /path/to/video.mp4"
echo "   3. 运行: drama-processor ai check-compliance /path/to/video.mp4"
echo "   4. 查看详细文档: docs/AI_SETUP_GUIDE.md"
echo ""
echo "🚀 开始享受简化版AI功能吧！"
echo ""
echo "💡 提示: 这是简化版本，暂时移除了以下功能："
echo "   - 视频质量评估"
echo "   - 文字内容检测（OCR）"
echo "   - 音频内容检测"
echo "   - 对话停顿检测"
echo "   - 动作高潮检测"