@echo off
chcp 65001 >nul
title 短剧剪辑工具 - 打包工具

echo ========================================
echo    短剧剪辑工具 - 打包工具
echo ========================================
echo.

cd /d %~dp0

echo 请选择打包对象：
echo.
echo [1] 小红（xh）
echo [2] 小李（xl）
echo [3] 小雪（xx）
echo [4] 自定义
echo [0] 退出
echo.

set /p choice=请输入选项 (0-4): 

if "%choice%"=="1" (
    set name=小红
) else if "%choice%"=="2" (
    set name=小李
) else if "%choice%"=="3" (
    set name=小雪
) else if "%choice%"=="4" (
    set /p name=请输入达人名称: 
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

PowerShell -NoProfile -ExecutionPolicy Bypass -Command "& {.\打包给达人.ps1 -达人名称 '%name%' -输出目录 'D:\打包输出'}"

echo.
echo 打包完成！
pause
