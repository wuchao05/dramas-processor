@echo off
REM Auto-detect and use PowerShell for better Unicode/emoji support

REM Check if PowerShell is available
where powershell.exe >nul 2>&1
if %errorlevel% equ 0 (
    echo Starting installation in PowerShell...
    echo.
    start "Drama Processor - Installation" powershell.exe -NoExit -Command "& {Set-Location '%~dp0drama-processor'; Write-Host '========================================' -ForegroundColor Cyan; Write-Host '  Drama Processor - Installation' -ForegroundColor Cyan; Write-Host '========================================' -ForegroundColor Cyan; Write-Host ''; Write-Host 'Starting installation...' -ForegroundColor Yellow; Write-Host ''; & '.\install.ps1'}"
    exit /b 0
)

REM Fallback to CMD if PowerShell is not available
chcp 65001 >nul
title Drama Processor - Install

echo ========================================
echo   Drama Processor - Installation
echo ========================================
echo.
echo Starting installation...
echo.
echo Note: PowerShell not found. Using CMD (limited Unicode support).
echo.

REM Run PowerShell install script (this should not happen on modern Windows)
cd /d "%~dp0drama-processor"
if exist install.ps1 (
    powershell -NoProfile -ExecutionPolicy Bypass -File ".\install.ps1"
) else (
    echo ERROR: install.ps1 not found!
    pause
    exit /b 1
)

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
