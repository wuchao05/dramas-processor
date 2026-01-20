@echo off
chcp 65001 >nul
title Drama Processor - Install

echo ========================================
echo   Drama Processor - Installation
echo ========================================
echo.
echo Starting installation...
echo.

REM Run PowerShell install script
powershell -NoProfile -ExecutionPolicy Bypass -Command "& '%~dp0drama-processor\install.ps1'"

if errorlevel 1 (
    echo.
    echo ========================================
    echo   Installation Failed
    echo ========================================
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Installation Complete
echo ========================================
pause
