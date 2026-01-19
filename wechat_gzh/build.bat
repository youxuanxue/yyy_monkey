@echo off
chcp 65001 >nul
REM 微信公众号自动评论机器人 - 一键打包脚本 (Windows)
REM
REM 使用方法：双击运行或在命令行执行 build.bat

echo ==============================================
echo 微信公众号自动评论机器人 - 一键打包
echo ==============================================

REM 进入脚本所在目录
cd /d "%~dp0"

REM 检查 uv 是否安装
where uv >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo 错误: 未找到 uv
    echo 请先安装: pip install uv
    pause
    exit /b 1
)

echo.
echo [1/3] 同步依赖...
uv sync

echo.
echo [2/3] 开始打包...
uv run python build.py

echo.
echo [3/3] 打包完成！
echo.
echo 输出目录: dist\
echo.
echo 请将 dist 目录压缩后分发给用户。
pause
