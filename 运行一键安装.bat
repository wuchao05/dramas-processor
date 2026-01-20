@echo off
chcp 65001 >nul
title 运行一键安装

echo ========================================
echo   Drama Processor - 一键安装
echo ========================================
echo.
echo 正在启动安装程序...
echo.

REM 使用 PowerShell 运行安装脚本（在项目文件目录中）
powershell -ExecutionPolicy Bypass -File "%~dp0项目文件\一键安装.ps1"

if errorlevel 1 (
    echo.
    echo ========================================
    echo   安装失败
    echo ========================================
    echo.
    echo 可能原因：
    echo   1. PowerShell 未正确安装
    echo   2. 权限不足
    echo.
    echo 解决方法：
    echo   1. 右键点击此文件
    echo   2. 选择"以管理员身份运行"
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo   安装完成
echo ========================================
pause
