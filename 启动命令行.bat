@echo off
chcp 65001 > nul
echo ======================================
echo   Drama Processor - Windows 版本
echo ======================================
echo.

REM 检查虚拟环境
if not exist "venv\Scripts\python.exe" (
    echo ❌ 虚拟环境未设置
    echo.
    echo 请先运行设置脚本：
    echo   powershell -ExecutionPolicy Bypass -File setup_windows.ps1
    echo.
    pause
    exit /b 1
)

REM 激活虚拟环境并显示帮助
echo 激活虚拟环境...
call venv\Scripts\activate.bat

echo.
echo ✅ 环境已激活！
echo.
echo 📚 常用命令：
echo   处理单个短剧：
echo     python -m drama_processor process "E:\短剧\我的剧集"
echo.
echo   批量处理：
echo     python -m drama_processor process "E:\短剧剪辑\源素材视频"
echo.
echo   查看飞书列表：
echo     python -m drama_processor feishu list
echo.
echo   监听飞书（自动处理）：
echo     python -m drama_processor feishu watch
echo.
echo   查看所有命令：
echo     python -m drama_processor --help
echo.
echo 💡 完整使用教程：docs\WINDOWS_使用教程.md
echo.

cmd /k
