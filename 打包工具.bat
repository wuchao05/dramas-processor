@echo off
chcp 65001 >nul
title 短剧剪辑工具 - 打包工具

echo ========================================
echo    短剧剪辑工具 - 打包工具
echo ========================================
echo.

cd /d %~dp0

echo 请选择打包对象（配置文件名称）：
echo.
echo [1] xh
echo [2] xl
echo [3] xx
echo [4] 自定义
echo [0] 退出
echo.
echo 提示：输入的名称需要在 configs\users\ 目录下有对应的 .yaml 配置文件
echo       例如输入 xh，需要有 configs\users\xh.yaml 文件
echo.

set /p choice=请输入选项 (0-4): 

if "%choice%"=="1" (
    set name=xh
) else if "%choice%"=="2" (
    set name=xl
) else if "%choice%"=="3" (
    set name=xx
) else if "%choice%"=="4" (
    set /p name=请输入配置名称（如 xh）: 
) else if "%choice%"=="0" (
    exit
) else (
    echo 无效选项！
    pause
    exit
)

echo.
echo 正在为 %name% 打包...
echo.

PowerShell -NoProfile -ExecutionPolicy Bypass -Command "& {.\打包给达人.ps1 -Name '%name%' -OutputDir 'D:\打包输出'}"

echo.
echo 打包完成！
pause
