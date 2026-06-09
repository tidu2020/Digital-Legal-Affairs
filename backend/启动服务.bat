
@echo off
chcp 65001 >nul
title 国企法务助手 - FastAPI 服务

echo ========================================
echo   国企法务助手 - FastAPI 服务启动器
echo ========================================
echo.

cd /d "%~dp0"

echo [1/3] 检查 Python 环境...
python --version
if %errorlevel% neq 0 (
    echo 错误: 未找到 Python，请先安装 Python
    pause
    exit /b 1
)
echo ✓ Python 环境正常
echo.

echo [2/3] 检查依赖...
python -c "import fastapi, uvicorn" 2>nul
if %errorlevel% neq 0 (
    echo 正在安装依赖...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo 错误: 依赖安装失败
        pause
        exit /b 1
    )
)
echo ✓ 依赖检查完成
echo.

echo [3/3] 启动 FastAPI 服务...
echo.
echo ========================================
echo   服务访问地址
echo ========================================
echo   主页:      http://127.0.0.1:1824
echo   API文档:   http://127.0.0.1:1824/docs
echo   健康检查:  http://127.0.0.1:1824/api/health
echo ========================================
echo.
echo 服务正在启动中...
echo 按 Ctrl+C 可停止服务
echo.

python -m uvicorn app:app --host 0.0.0.0 --port 1824

if %errorlevel% neq 0 (
    echo.
    echo 服务异常退出，错误代码: %errorlevel%
    pause
)
