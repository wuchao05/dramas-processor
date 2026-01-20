@echo off
chcp 65001 >nul
title Drama Processor - Package Tool

echo ========================================
echo    Drama Processor - Package Tool
echo ========================================
echo.

cd /d %~dp0

REM Check configs\users directory
if not exist "configs\users\" (
    echo ERROR: configs\users\ directory not found!
    pause
    exit /b 1
)

echo Scanning available user configs...
echo.
echo Please select package target:
echo.

REM Scan YAML files and generate menu
setlocal enabledelayedexpansion
set index=0
set "configs="

REM Loop through configs\users\*.yaml (exclude *-daily.yaml)
for %%f in (configs\users\*.yaml) do (
    set "filename=%%~nf"
    REM Exclude -daily files
    echo !filename! | findstr /C:"-daily" >nul
    if errorlevel 1 (
        set /a index+=1
        echo [!index!] !filename!
        set "config_!index!=!filename!"
        if defined configs (
            set "configs=!configs!,!filename!"
        ) else (
            set "configs=!filename!"
        )
    )
)

if %index%==0 (
    echo ERROR: No config files found in configs\users\!
    echo Please ensure .yaml files exist (e.g. xh.yaml)
    pause
    exit /b 1
)

echo.
echo [0] Exit
echo.

set /p choice=Enter option (0-%index%): 

if "%choice%"=="0" (
    exit /b 0
)

REM Validate input
set "name="
if %choice% geq 1 if %choice% leq %index% (
    set "name=!config_%choice%!"
) else (
    echo Invalid option!
    pause
    exit /b 1
)

echo.
echo Packaging for: %name%
echo.

PowerShell -NoProfile -ExecutionPolicy Bypass -Command "& {.\package.ps1 -Name '%name%' -OutputDir 'D:\Package-Output'}"

if %errorlevel% neq 0 (
    echo.
    echo Packaging failed! Please check error messages.
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Package Complete!
echo   Config: %name%
echo   Output: D:\Package-Output
echo ========================================
pause
