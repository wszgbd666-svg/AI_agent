@echo off
chcp 65001 >nul
cd /d %~dp0
set "PY=D:\DevTools\Python\Miniconda3\envs\ai\python.exe"
set PYTHONIOENCODING=utf-8
if not exist "%PY%" (
  echo [错误] 找不到 ai 环境的 Python:
  echo        %PY%
  echo 请确认 conda 的 ai 环境存在,或修改 start.bat 第 4 行的路径。
  pause
  exit /b 1
)
echo 社区养老便民助手: http://localhost:8090
start "" http://localhost:8090
%PY% app.py
pause
