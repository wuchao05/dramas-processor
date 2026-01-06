#!/bin/bash
# WSL 内存守护脚本 - 防止内存占用过高

echo "🛡️  WSL 内存守护脚本启动"
echo "每 5 分钟检查一次内存，超过阈值自动清理"
echo "按 Ctrl+C 停止"
echo ""

THRESHOLD_PERCENT=70  # 内存使用超过 70% 时清理

while true; do
    # 获取内存使用百分比
    MEM_USED_PERCENT=$(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100}')
    MEM_USED_GB=$(free -h | grep Mem | awk '{print $3}')
    MEM_TOTAL_GB=$(free -h | grep Mem | awk '{print $2}')
    
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    
    if [ "$MEM_USED_PERCENT" -gt "$THRESHOLD_PERCENT" ]; then
        echo "[$TIMESTAMP] ⚠️  内存占用过高：$MEM_USED_GB / $MEM_TOTAL_GB ($MEM_USED_PERCENT%)"
        echo "[$TIMESTAMP] 🧹 正在清理缓存..."
        
        # 清理页面缓存
        sudo sh -c 'echo 3 > /proc/sys/vm/drop_caches' 2>/dev/null
        
        # 等待一秒后再次检查
        sleep 1
        NEW_PERCENT=$(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100}')
        NEW_USED=$(free -h | grep Mem | awk '{print $3}')
        
        echo "[$TIMESTAMP] ✅ 清理完成：$NEW_USED ($NEW_PERCENT%)"
        echo ""
    else
        echo "[$TIMESTAMP] ✓ 内存正常：$MEM_USED_GB / $MEM_TOTAL_GB ($MEM_USED_PERCENT%)"
    fi
    
    # 等待 5 分钟
    sleep 300
done

