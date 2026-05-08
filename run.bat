@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo ========================================
echo    磁盘优化器 Professional
echo ========================================
echo.

REM 检查Python是否安装
set PYTHON_CMD=
python --version >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=python
) else (
    py --version >nul 2>&1
    if %errorlevel% equ 0 (
        set PYTHON_CMD=py
    ) else (
        python3 --version >nul 2>&1
        if %errorlevel% equ 0 (
            set PYTHON_CMD=python3
        )
    )
)

if "%PYTHON_CMD%"=="" (
    echo [错误] 未检测到Python，请先安装Python
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM 强制 Python 使用 UTF-8 编码读取源文件
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

REM 运行程序
%PYTHON_CMD% run.py

pause
