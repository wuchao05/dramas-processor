@echo off
chcp 65001 >nul
title 短剧剪辑工具 - 飞书自动监控（XH账号）

echo ========================================
echo    短剧剪辑工具 - 飞书自动监控
echo    账号：XH（小红）
echo ========================================
echo.

cd /d %~dp0
call venv\Scripts\activate.bat

echo [√] 虚拟环境已激活
echo [√] 正在启动飞书监控...
echo.
echo 提示：
echo - 按 Ctrl+C 可以安全停止
echo - 窗口会显示实时处理进度
echo.

python -m drama_processor feishu watch --config configs/users/xh-daily.yaml

echo.
echo ========================================
echo    监控已停止
echo ========================================
pause
