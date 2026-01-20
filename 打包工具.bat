@echo off
chcp 65001 >nul
title 短剧剪辑工具 - 打包工具

echo ========================================
echo    短剧剪辑工具 - 打包工具
echo ========================================
echo.

cd /d %~dp0

REM 检查 configs\users 目录是否存在
if not exist "configs\users\" (
    echo 错误：找不到 configs\users\ 目录！
    pause
    exit /b 1
)

echo 正在扫描可用的达人配置...
echo.
echo 请选择打包对象：
echo.

REM 动态读取配置文件并生成菜单
setlocal enabledelayedexpansion
set index=0
set "configs="

REM 遍历 configs\users 目录下的 .yaml 文件（排除 *-daily.yaml）
for %%f in (configs\users\*.yaml) do (
    set "filename=%%~nf"
    REM 排除 -daily 结尾的文件
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
    echo 错误：configs\users\ 目录下没有找到任何配置文件！
    echo 请确保目录下有 .yaml 配置文件（例如 xh.yaml）
    pause
    exit /b 1
)

echo.
echo [0] 退出
echo.

set /p choice=请输入选项 (0-%index%): 

if "%choice%"=="0" (
    exit /b 0
)

REM 验证输入
set "name="
if %choice% geq 1 if %choice% leq %index% (
    set "name=!config_%choice%!"
) else (
    echo 无效选项！
    pause
    exit /b 1
)

echo.
echo 正在为 %name% 打包...
echo.

PowerShell -NoProfile -ExecutionPolicy Bypass -Command "& {.\打包给达人.ps1 -Name '%name%' -OutputDir 'D:\打包输出'}"

if %errorlevel% neq 0 (
    echo.
    echo 打包失败！请检查错误信息。
    pause
    exit /b 1
)

echo.
echo ========================================
echo   打包完成！
echo   配置：%name%
echo   输出：D:\打包输出
echo ========================================
pause
