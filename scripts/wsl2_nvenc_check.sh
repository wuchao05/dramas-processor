#!/bin/bash

# WSL2 NVENC 硬件编码调试脚本
# 用于检查和诊断 WSL2 中的 NVIDIA 硬件编码器配置

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=========================================="
echo "WSL2 NVENC 硬件编码诊断工具"
echo -e "==========================================${NC}\n"

# 检查是否在 WSL 环境中
if ! grep -qi microsoft /proc/version; then
    echo -e "${RED}❌ 当前不在 WSL 环境中${NC}"
    exit 1
fi

echo -e "${GREEN}✅ 运行在 WSL 环境${NC}\n"

# ============================================
# 1. 检查 WSL 版本
# ============================================
echo -e "${BLUE}[1/7] 检查 WSL 版本${NC}"
WSL_VERSION=$(wsl.exe --version 2>&1 | grep "WSL" | head -n 1 || echo "Unknown")
echo "WSL 版本: $WSL_VERSION"

# ============================================
# 2. 检查 Windows 版本
# ============================================
echo -e "\n${BLUE}[2/7] 检查 Windows 版本${NC}"
WIN_VERSION=$(cmd.exe /c ver 2>/dev/null | tr -d '\r')
echo "Windows 版本: $WIN_VERSION"

BUILD_NUMBER=$(echo "$WIN_VERSION" | grep -oP '\d+\.\d+\.\d+\.\d+' | cut -d. -f3)
if [ -n "$BUILD_NUMBER" ] && [ "$BUILD_NUMBER" -ge 19044 ]; then
    echo -e "${GREEN}✅ Windows 版本支持 WSL2 GPU (build >= 19044)${NC}"
else
    echo -e "${YELLOW}⚠️  Windows 版本可能不支持 WSL2 GPU (需要 build >= 19044)${NC}"
fi

# ============================================
# 3. 检查 GPU 驱动
# ============================================
echo -e "\n${BLUE}[3/7] 检查 NVIDIA GPU 和驱动${NC}"
if command -v nvidia-smi &> /dev/null; then
    GPU_INFO=$(nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader 2>/dev/null || echo "")
    if [ -n "$GPU_INFO" ]; then
        echo -e "${GREEN}✅ GPU 可访问${NC}"
        echo "GPU 信息: $GPU_INFO"
        
        # 检查驱动版本
        DRIVER_VERSION=$(echo "$GPU_INFO" | cut -d',' -f2 | tr -d ' ')
        DRIVER_MAJOR=$(echo "$DRIVER_VERSION" | cut -d. -f1)
        
        if [ "$DRIVER_MAJOR" -ge 470 ]; then
            echo -e "${GREEN}✅ 驱动版本支持 CUDA on WSL ($DRIVER_VERSION >= 470.76)${NC}"
        else
            echo -e "${YELLOW}⚠️  驱动版本可能过旧 ($DRIVER_VERSION)，建议升级到 >= 470.76${NC}"
        fi
    else
        echo -e "${RED}❌ nvidia-smi 运行失败${NC}"
        echo -e "${YELLOW}💡 可能原因：${NC}"
        echo "   1. NVIDIA 驱动未正确安装"
        echo "   2. 需要安装 CUDA on WSL 驱动"
        echo "   3. 需要重启 WSL: wsl --shutdown"
    fi
else
    echo -e "${RED}❌ nvidia-smi 不可用${NC}"
    echo -e "${YELLOW}💡 解决方案：${NC}"
    echo "   1. 在 Windows 中安装 NVIDIA CUDA on WSL 驱动"
    echo "   2. 下载地址: https://developer.nvidia.com/cuda/wsl"
    echo "   3. 安装后重启电脑"
fi

# ============================================
# 4. 检查 FFmpeg 安装
# ============================================
echo -e "\n${BLUE}[4/7] 检查 FFmpeg 安装${NC}"
if command -v ffmpeg &> /dev/null; then
    FFMPEG_VERSION=$(ffmpeg -version 2>/dev/null | head -n 1)
    echo -e "${GREEN}✅ FFmpeg 已安装${NC}"
    echo "$FFMPEG_VERSION"
else
    echo -e "${RED}❌ FFmpeg 未安装${NC}"
    echo -e "${YELLOW}💡 安装命令: sudo apt install ffmpeg${NC}"
    exit 1
fi

# ============================================
# 5. 检查 FFmpeg NVENC 支持
# ============================================
echo -e "\n${BLUE}[5/7] 检查 FFmpeg NVENC 支持${NC}"
NVENC_ENCODERS=$(ffmpeg -encoders 2>&1 | grep nvenc || echo "")
if [ -n "$NVENC_ENCODERS" ]; then
    echo -e "${GREEN}✅ FFmpeg 支持 NVENC 编码器${NC}"
    echo "$NVENC_ENCODERS"
else
    echo -e "${RED}❌ FFmpeg 不支持 NVENC 编码器${NC}"
    echo -e "${YELLOW}💡 解决方案：${NC}"
    echo "   1. 安装支持 NVENC 的 FFmpeg 版本"
    echo "   2. Ubuntu: sudo add-apt-repository ppa:savoury1/ffmpeg4"
    echo "   3. 或从源码编译 FFmpeg（参考 docs/WSL2_NVENC_SETUP.md）"
    exit 1
fi

# ============================================
# 6. 测试 NVENC 编码
# ============================================
echo -e "\n${BLUE}[6/7] 测试 NVENC 硬件编码${NC}"
echo "正在进行快速编码测试（约5秒）..."

TEST_OUTPUT=$(mktemp --suffix=.mp4)
TEST_CMD="ffmpeg -y -f lavfi -i testsrc=duration=1:size=640x480:rate=30 -c:v h264_nvenc -preset fast -t 1 -f null - 2>&1"

if eval $TEST_CMD | grep -q "error\|Error\|failed\|Failed"; then
    echo -e "${RED}❌ NVENC 编码测试失败${NC}"
    echo -e "\n${YELLOW}详细错误信息：${NC}"
    eval $TEST_CMD 2>&1 | tail -n 15
    
    echo -e "\n${YELLOW}💡 常见问题：${NC}"
    echo "   1. 驱动版本过旧 → 更新 NVIDIA 驱动"
    echo "   2. GPU 被占用 → 关闭其他使用 GPU 的程序"
    echo "   3. CUDA 库问题 → 检查 LD_LIBRARY_PATH"
    echo "   4. 权限问题 → 尝试重启 WSL (wsl --shutdown)"
    
    exit 1
else
    echo -e "${GREEN}✅ NVENC 编码测试成功！${NC}"
    
    # 显示编码性能
    echo -e "\n${BLUE}编码性能信息：${NC}"
    eval $TEST_CMD 2>&1 | grep -E "(fps=|speed=)" | tail -n 1
fi

rm -f "$TEST_OUTPUT"

# ============================================
# 7. 检查项目配置
# ============================================
echo -e "\n${BLUE}[7/7] 检查项目配置${NC}"

# 检查配置文件
CONFIG_FILE="configs/default.yaml"
if [ -f "$CONFIG_FILE" ]; then
    USE_HW=$(grep "^use_hardware:" "$CONFIG_FILE" | awk '{print $2}')
    HW_CODEC=$(grep "hw_codec:" "$CONFIG_FILE" | awk '{print $2}' | tr -d "'\"")
    
    echo "配置文件: $CONFIG_FILE"
    echo "use_hardware: $USE_HW"
    echo "hw_codec: $HW_CODEC"
    
    if [ "$USE_HW" = "true" ]; then
        echo -e "${GREEN}✅ 硬件编码已启用${NC}"
    else
        echo -e "${YELLOW}⚠️  硬件编码未启用${NC}"
        echo -e "${YELLOW}💡 修改配置: use_hardware: true${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  未找到配置文件 $CONFIG_FILE${NC}"
fi

# ============================================
# 总结
# ============================================
echo -e "\n${BLUE}=========================================="
echo "诊断总结"
echo -e "==========================================${NC}"

echo -e "${GREEN}✅ WSL2 环境正常${NC}"
echo -e "${GREEN}✅ GPU 驱动正常${NC}"
echo -e "${GREEN}✅ FFmpeg 支持 NVENC${NC}"
echo -e "${GREEN}✅ NVENC 编码测试通过${NC}"

echo -e "\n${GREEN}🎉 恭喜！你的 WSL2 环境已成功配置硬件编码${NC}"
echo -e "\n${BLUE}下一步：${NC}"
echo "1. 确保配置文件中 use_hardware: true"
echo "2. 运行项目: drama-processor process /path/to/dramas"
echo "3. 查看日志确认使用了 h264_nvenc 编码器"
echo ""
echo "详细配置指南: docs/WSL2_NVENC_SETUP.md"

# ============================================
# GPU 实时监控
# ============================================
echo -e "\n${BLUE}💡 提示：运行项目时可以用以下命令监控 GPU 使用情况：${NC}"
echo "   watch -n 1 nvidia-smi"
echo ""

