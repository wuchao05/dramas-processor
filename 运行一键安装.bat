@echo off
chcp 65001 >nul
title 运行一键安装

echo ========================================
echo   Drama Processor - 一键安装
echo ========================================
echo.
echo 正在启动安装程序...
echo.

REM 使用 PowerShell 运行安装脚本（避免 BOM 问题）
powershell -NoProfile -ExecutionPolicy Bypass -Command "& '%~dp0项目文件\一键安装.ps1'"

if errorlevel 1 (
    echo.
    echo ========================================
    echo   安装失败
    echo ========================================
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo   安装完成
echo ========================================
pause
