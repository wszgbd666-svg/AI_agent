@echo off
chcp 65001 >nul
rem 开机自启用:隐藏窗口启动 DSH,自动打开浏览器,日志写到 .dsh\dsh-web.log
for /f "tokens=1,* delims==" %%a in (D:\AI_agent\partner\.env) do (
  if "%%a"=="DEEPSEEK_API_KEY" set "DEEPSEEK_API_KEY=%%b"
)
dsh --profile web >> "%USERPROFILE%\.dsh\dsh-web.log" 2>&1
