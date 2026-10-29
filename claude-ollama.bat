@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
REM ============================================
REM  本地 Ollama 版 Claude Code 启动脚本
REM  用法: claude-ollama.bat [Claude Code 参数]
REM  依赖: Ollama 桌面版已运行 + conda 环境 litellm 已装
REM ============================================
cd /d %~dp0

REM --- 1. 检查 Ollama 是否在运行 ---
curl -s --max-time 2 http://127.0.0.1:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo [错误] Ollama 未运行, 请先启动 Ollama 桌面版
    pause
    exit /b 1
)

REM --- 2. 网关未运行则拉起, 并等待就绪(最多30秒) ---
curl -s --max-time 2 http://127.0.0.1:3456/health/liveliness >nul 2>&1
if errorlevel 1 (
    echo [litellm] 正在启动网关...
    start "litellm-gateway" /min cmd /c "D:\DevTools\Python\Miniconda3\envs\litellm\Scripts\litellm.exe --config C:\Users\Administrator\.litellm\config-ollama.yaml --port 3456"
    set /a tries=0
    :wait_gateway
    timeout /t 1 /nobreak >nul
    curl -s --max-time 2 http://127.0.0.1:3456/health/liveliness >nul 2>&1
    if errorlevel 1 (
        set /a tries+=1
        if !tries! lss 30 goto wait_gateway
        echo [警告] 网关启动超时, 继续尝试连接
    )
)

REM --- 3. 用 Ollama 专用配置启动 Claude Code ---
claude --settings "%USERPROFILE%\.claude\settings-ollama.json" %*
