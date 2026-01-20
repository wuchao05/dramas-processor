@echo off
setlocal enabledelayedexpansion
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
set index=0

REM Loop through configs\users\*.yaml (exclude *-daily.yaml)
for %%f in (configs\users\*.yaml) do (
    set "filename=%%~nf"
    REM Exclude -daily files
    echo !filename! | findstr /C:"-daily" >nul
    if errorlevel 1 (
        set /a index+=1
        echo [!index!] !filename!
        set "config_!index!=!filename!"
    )
)

echo.
echo [0] Exit
echo.

REM Check if any configs found
if !index! EQU 0 (
    echo ERROR: No config files found in configs\users\!
    echo Please ensure .yaml files exist (e.g. xh.yaml)
    pause
    exit /b 1
)

REM Read user input
set /p choice=Enter option (0-!index!): 

REM Check if empty
if "!choice!"=="" (
    echo ERROR: No option entered!
    pause
    exit /b 1
)

REM Check for exit
if "!choice!"=="0" (
    echo Exiting...
    exit /b 0
)

REM Validate numeric input
set /a test=!choice! 2>nul
if !test! LSS 1 (
    echo ERROR: Invalid option! Please enter a number between 1 and !index!
    pause
    exit /b 1
)
if !test! GTR !index! (
    echo ERROR: Invalid option! Please enter a number between 1 and !index!
    pause
    exit /b 1
)

REM Get config name
call set "name=%%config_!choice!%%"

REM Check if name was set
if "!name!"=="" (
    echo ERROR: Failed to get config name!
    echo DEBUG: choice=!choice!, index=!index!
    pause
    exit /b 1
)

echo.
echo Packaging for: !name!
echo.

REM Call PowerShell packaging script
PowerShell -NoProfile -ExecutionPolicy Bypass -Command "& {.\package.ps1 -Name '!name!' -OutputDir 'D:\Package-Output'}"

if errorlevel 1 (
    echo.
    echo ERROR: Packaging failed! Please check error messages above.
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
