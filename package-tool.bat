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

REM Check if any configs found (use delayed expansion)
if !index!==0 (
    echo ERROR: No config files found in configs\users\!
    echo Please ensure .yaml files exist (e.g. xh.yaml)
    pause
    exit /b 1
)

echo.
echo [0] Exit
echo.

REM Read user input (use delayed expansion)
set /p choice=Enter option (0-!index!): 

REM Debug: Show what was entered
echo.
echo [DEBUG] You entered: !choice!
echo [DEBUG] Total configs: !index!

if "!choice!"=="0" (
    echo Exiting...
    exit /b 0
)

REM Validate input (use delayed expansion)
set "name="
if !choice! geq 1 if !choice! leq !index! (
    call set "name=%%config_!choice!%%"
    echo [DEBUG] Selected config: !name!
) else (
    echo.
    echo ERROR: Invalid option! Please enter a number between 0 and !index!
    pause
    exit /b 1
)

REM Check if name was set correctly
if "!name!"=="" (
    echo.
    echo ERROR: Failed to get config name!
    pause
    exit /b 1
)

echo.
echo Packaging for: !name!
echo.

REM Call PowerShell packaging script
PowerShell -NoProfile -ExecutionPolicy Bypass -Command "& {.\package.ps1 -Name '!name!' -OutputDir 'D:\Package-Output'}"

if %errorlevel% neq 0 (
    echo.
    echo Packaging failed! Please check error messages.
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Package Complete!
echo   Config: !name!
echo   Output: D:\Package-Output
echo ========================================
pause
