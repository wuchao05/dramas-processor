@echo off
REM 保留白名单中的顶层目录（每个剧=一个顶层目录），其余清理/移动
REM 用法：
REM   keep-show.bat "D:\dramas"                    # 预演（不删除）
REM   keep-show.bat "D:\dramas" --apply            # 真删/真移动
REM   可选： --to "D:\_Recycle"                    # 不直接删，先移到回收目录

setlocal enabledelayedexpansion

REM 参数解析
set "SOURCE_PATH="
set "APPLY=0"
set "MOVE_TO="
set "CASE_INS=0"

:parse_args
if "%~1"=="" goto :validate_args
if "%~1"=="--apply" (
    set "APPLY=1"
    shift
    goto :parse_args
)
if "%~1"=="--to" (
    set "MOVE_TO=%~2"
    shift
    shift
    goto :parse_args
)
if "%~1"=="--case-insensitive" (
    set "CASE_INS=1"
    shift
    goto :parse_args
)
if "%~1"=="--help" (
    echo 用法:
    echo   keep-show.bat "源目录路径" [选项]
    echo.
    echo 选项:
    echo   --apply              真正执行删除/移动
    echo   --to "目标路径"      移动到指定目录而不是删除
    echo   --case-insensitive   忽略大小写匹配
    echo   --help              显示帮助信息
    echo.
    echo 示例:
    echo   keep-show.bat "D:\dramas"
    echo   keep-show.bat "D:\dramas" --apply
    echo   keep-show.bat "D:\dramas" --apply --to "D:\_Recycle"
    exit /b 0
)
if not defined SOURCE_PATH (
    set "SOURCE_PATH=%~1"
    shift
    goto :parse_args
)
shift
goto :parse_args

:validate_args
if not defined SOURCE_PATH (
    echo [ERR] 请输入源目录路径
    exit /b 1
)
if not exist "%SOURCE_PATH%" (
    echo [ERR] 源目录不存在：%SOURCE_PATH%
    exit /b 1
)
if defined MOVE_TO (
    if not exist "%MOVE_TO%" (
        mkdir "%MOVE_TO%" 2>nul
        if errorlevel 1 (
            echo [ERR] 无法创建移动目标目录：%MOVE_TO%
            exit /b 1
        )
    )
)

REM 创建临时文件
set "TEMP_DIR=%TEMP%\keep-show-%RANDOM%"
mkdir "%TEMP_DIR%" 2>nul
set "WL_FILE=%TEMP_DIR%\whitelist.txt"
set "AVAIL_FILE=%TEMP_DIR%\available.txt"
set "MISS_FILE=%TEMP_DIR%\missing.txt"

REM 清理函数
:cleanup
if exist "%TEMP_DIR%" rmdir /s /q "%TEMP_DIR%" 2>nul
exit /b %1

REM 读取白名单（从剪贴板）
echo [INFO] 正在读取剪贴板内容...
powershell -Command "Get-Clipboard" > "%WL_FILE%" 2>nul
if errorlevel 1 (
    echo [ERR] 无法读取剪贴板内容
    goto :cleanup 1
)

REM 处理白名单（去除空行，处理大小写）
if %CASE_INS%==1 (
    powershell -Command "Get-Content '%WL_FILE%' | Where-Object { $_.Trim() -ne '' } | ForEach-Object { $_.ToLower() } | Sort-Object -Unique" > "%WL_FILE%.tmp"
) else (
    powershell -Command "Get-Content '%WL_FILE%' | Where-Object { $_.Trim() -ne '' } | Sort-Object -Unique" > "%WL_FILE%.tmp"
)
move "%WL_FILE%.tmp" "%WL_FILE%" >nul

REM 检查白名单是否为空
for /f %%i in ('type "%WL_FILE%" ^| find /c /v ""') do set "WL_COUNT=%%i"
if %WL_COUNT%==0 (
    echo [ERR] 白名单为空
    goto :cleanup 1
)

echo ======= 白名单（共 %WL_COUNT% 条）示例 =======
powershell -Command "Get-Content '%WL_FILE%' | Select-Object -First 10 | ForEach-Object { Write-Host $_ }"
if %WL_COUNT% gtr 10 echo (仅展示前 10 条...)
echo =============================================

REM 扫描源目录
echo [INFO] 正在扫描顶层目录：%SOURCE_PATH% ...
for /f %%i in ('dir /b /ad "%SOURCE_PATH%" ^| find /c /v ""') do set "TOTAL_DIRS=%%i"
echo [INFO] 顶层目录数量：%TOTAL_DIRS%

REM 构建可用目录列表
echo. > "%AVAIL_FILE%"
for /f "delims=" %%d in ('dir /b /ad "%SOURCE_PATH%"') do (
    set "dir_name=%%d"
    if %CASE_INS%==1 (
        for /f "delims=" %%n in ('powershell -Command "('%%d').ToLower()"') do echo %%n >> "%AVAIL_FILE%"
    ) else (
        echo %%d >> "%AVAIL_FILE%"
    )
)

REM 查找缺失的剧目
powershell -Command "Compare-Object (Get-Content '%WL_FILE%') (Get-Content '%AVAIL_FILE%') -IncludeEqual | Where-Object { $_.SideIndicator -eq '<=' } | ForEach-Object { $_.InputObject }" > "%MISS_FILE%"
for /f %%i in ('type "%MISS_FILE%" ^| find /c /v ""') do set "MISS_COUNT=%%i"

if %MISS_COUNT% gtr 0 (
    echo.
    echo ⚠️  以下白名单剧目在磁盘中【未找到】（共 %MISS_COUNT% 条，展示前 20 条）：
    powershell -Command "Get-Content '%MISS_FILE%' | Select-Object -First 20 | ForEach-Object { Write-Host '  ' $_ }"
    if %MISS_COUNT% gtr 20 echo (其余 %MISS_COUNT% 条已省略)
)

REM 分类目录
set "KEEP_COUNT=0"
set "DELETE_COUNT=0"

for /f "delims=" %%d in ('dir /b /ad "%SOURCE_PATH%"') do (
    set "dir_name=%%d"
    set "key=%%d"
    if %CASE_INS%==1 (
        for /f "delims=" %%k in ('powershell -Command "('%%d').ToLower()"') do set "key=%%k"
    )
    
    REM 检查是否在白名单中
    findstr /x /c:"!key!" "%WL_FILE%" >nul
    if errorlevel 1 (
        set /a DELETE_COUNT+=1
        echo 将删除: %%d
    ) else (
        set /a KEEP_COUNT+=1
        echo 将保留: %%d
    )
)

echo.
echo [SUMMARY] 将保留目录数：%KEEP_COUNT%
echo [SUMMARY] 将清理目录数：%DELETE_COUNT%

if %APPLY%==0 (
    echo.
    echo 【Dry-run 预演】以上目录将被清理（不执行删除/移动）
    echo 要真正执行，请加：--apply
    if defined MOVE_TO echo 当前设置为移动到：%MOVE_TO%
    goto :cleanup 0
)

echo.
echo 【执行中】开始处理未在白名单中的目录...

for /f "delims=" %%d in ('dir /b /ad "%SOURCE_PATH%"') do (
    set "dir_name=%%d"
    set "key=%%d"
    if %CASE_INS%==1 (
        for /f "delims=" %%k in ('powershell -Command "('%%d').ToLower()"') do set "key=%%k"
    )
    
    findstr /x /c:"!key!" "%WL_FILE%" >nul
    if errorlevel 1 (
        if defined MOVE_TO (
            set "timestamp=%date:~0,4%%date:~5,2%%date:~8,2%-%time:~0,2%%time:~3,2%%time:~6,2%"
            set "timestamp=!timestamp: =0!"
            echo   移动：%%d
            move "%%d" "%MOVE_TO%\%%d__!timestamp!" >nul
        ) else (
            echo   删除：%%d
            rmdir /s /q "%%d"
        )
    )
)

echo 完成 ✅
goto :cleanup 0
