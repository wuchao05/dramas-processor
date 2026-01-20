@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

echo Starting test...
echo.

cd /d %~dp0

REM Test 1: Scan configs
echo [TEST 1] Scanning configs...
set index=0

for %%f in (configs\users\*.yaml) do (
    set "filename=%%~nf"
    echo !filename! | findstr /C:"-daily" >nul
    if errorlevel 1 (
        set /a index+=1
        echo [!index!] !filename!
        set "config_!index!=!filename!"
    )
)

echo.
echo [TEST 2] Found !index! configs
echo.

REM Test 3: Show exit option
echo [0] Exit
echo.

REM Test 4: Read input
echo [TEST 3] About to read input...
set /p choice=Enter your choice: 
echo.

REM Test 5: Show what was entered
echo [TEST 4] You entered: !choice!
echo.

pause
