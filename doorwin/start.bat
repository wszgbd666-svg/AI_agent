@echo off
chcp 65001 >nul
cd /d "%~dp0"
set IP=
for /f "tokens=2 delims=:" %%i in ('ipconfig ^| findstr /c:"IPv4"') do set IP=%%i
set IP=%IP: =%
if "%IP%"=="" set IP=localhost
echo ============================================
echo   门窗效果图软件
echo   电脑访问: http://%IP%:8000
echo   手机打开: 页面右上角点 📱 扫二维码
echo   按 Ctrl+C 停止服务
echo ============================================
start "" http://%IP%:8000
python -m http.server 8000
pause
