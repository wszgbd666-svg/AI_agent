@echo off
chcp 65001 >nul
rem 从 partner/.env 自动读取 DeepSeek API Key(不打印)
for /f "tokens=1,* delims==" %%a in (D:\AI_agent\partner\.env) do (
  if "%%a"=="DEEPSEEK_API_KEY" set "DEEPSEEK_API_KEY=%%b"
)
if not defined DEEPSEEK_API_KEY (
  echo [警告] 没读到 DEEPSEEK_API_KEY,网页里首次发任务时需要手动填
)
dsh --profile web
pause
