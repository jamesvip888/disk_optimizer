@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ========================================
echo    依赖安装脚本
echo ========================================
echo.

REM 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python
    echo 请先安装 Python: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/3] 升级 pip...
echo ----------------------------------------
python -m pip install --upgrade pip
echo.

echo [2/3] 安装 PySide6...
echo ----------------------------------------
python -m pip install PySide6==6.6.1
if %errorlevel% neq 0 (
    echo [警告] PySide6 安装失败，尝试不指定版本...
    python -m pip install PySide6
)
echo.

echo [3/3] 安装 psutil...
echo ----------------------------------------
python -m pip install psutil==5.9.7
if %errorlevel% neq 0 (
    echo [警告] psutil 安装失败，尝试不指定版本...
    python -m pip install psutil
)
echo.

echo ========================================
echo    验证安装
echo ========================================
echo.

echo 检查 PySide6...
python -c "import PySide6; print('[OK] PySide6 已安装，版本:', PySide6.__version__)" 2>&1
if %errorlevel% neq 0 (
    echo [失败] PySide6 未正确安装
)

echo.
echo 检查 psutil...
python -c "import psutil; print('[OK] psutil 已安装，版本:', psutil.__version__)" 2>&1
if %errorlevel% neq 0 (
    echo [失败] psutil 未正确安装
)

echo.
echo ========================================
echo    安装完成
echo ========================================
echo.
echo 如果所有组件都显示 [OK]，可以运行 start.bat 启动程序
echo 如果有组件显示 [失败]，请查看上面的错误信息
echo.
pause