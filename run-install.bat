@echo off
REM Try to use Windows Terminal or PowerShell for better Unicode support

REM Check if Windows Terminal is available
where wt.exe >nul 2>&1
if %errorlevel% equ 0 (
    echo Starting installation in Windows Terminal...
    wt.exe -w 0 new-tab --title "Drama Processor - Installation" powershell.exe -NoExit -Command "cd '%~dp0drama-processor'; & '%~dp0drama-processor\install.ps1'; if ($LASTEXITCODE -eq 0) { Write-Host ''; Write-Host 'Installation completed! Press any key to close...' -ForegroundColor Green; pause } else { Write-Host ''; Write-Host 'Installation failed! Press any key to close...' -ForegroundColor Red; pause }"
    exit /b 0
)

REM Check if PowerShell is available
where powershell.exe >nul 2>&1
if %errorlevel% equ 0 (
    echo Starting installation in PowerShell...
    start "Drama Processor - Installation" powershell.exe -NoExit -Command "Write-Host '========================================' -ForegroundColor Cyan; Write-Host '  Drama Processor - Installation' -ForegroundColor Cyan; Write-Host '========================================' -ForegroundColor Cyan; Write-Host ''; Write-Host 'Starting installation...' -ForegroundColor Yellow; Write-Host ''; cd '%~dp0drama-processor'; & '%~dp0drama-processor\install.ps1'; if ($LASTEXITCODE -eq 0) { Write-Host ''; Write-Host '========================================' -ForegroundColor Green; Write-Host '  Installation Complete' -ForegroundColor Green; Write-Host '========================================' -ForegroundColor Green; pause } else { Write-Host ''; Write-Host '========================================' -ForegroundColor Red; Write-Host '  Installation Failed' -ForegroundColor Red; Write-Host '========================================' -ForegroundColor Red; pause }"
    exit /b 0
)

REM Fallback to CMD (default)
chcp 65001 >nul
title Drama Processor - Install

echo ========================================
echo   Drama Processor - Installation
echo ========================================
echo.
echo Starting installation...
echo.
echo Note: Using CMD. For better display, install Windows Terminal.
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
