@echo off
setlocal
cd /d "%~dp0"
set JDK=D:\DevTools\Java\jdk17
set BT=D:\DevTools\Android\build-tools\34.0.0
set ANDROID_JAR=D:\DevTools\Android\platforms\android-34\android.jar
set PATH=%JDK%\bin;%PATH%

set KSPASS=
if exist keystore.properties set /p KSPASS=<keystore.properties
if not defined KSPASS echo [ERROR] keystore.properties not found or empty & exit /b 1

echo [1/6] Compiling Java...
if exist build rmdir /s /q build
mkdir build\classes
"%JDK%\bin\javac.exe" -source 1.8 -target 1.8 -bootclasspath "%ANDROID_JAR%" -encoding UTF-8 -d build\classes java\com\doorwin\app\MainActivity.java
if errorlevel 1 goto :err

echo [2/6] Building dex...
"%JDK%\bin\jar.exe" cf build\classes.jar -C build\classes .
call "%BT%\d8.bat" --release --lib "%ANDROID_JAR%" --output build build\classes.jar
if errorlevel 1 goto :err

echo [3/6] Packaging resources and assets...
mkdir build\res-compiled
"%BT%\aapt2.exe" compile --dir res -o build\res-compiled\res.zip
if errorlevel 1 goto :err
"%BT%\aapt2.exe" link -o build\base.apk -I "%ANDROID_JAR%" --manifest AndroidManifest.xml -A assets build\res-compiled\res.zip --auto-add-overlay
if errorlevel 1 goto :err

echo [4/6] Fixing paths, adding dex, aligning...
python fixzip.py
if errorlevel 1 goto :err
"%BT%\zipalign.exe" -f 4 build\fixed.apk build\aligned.apk

echo [5/6] Creating signing key (first time only)...
if not exist doorwin.keystore "%JDK%\bin\keytool.exe" -genkeypair -keystore doorwin.keystore -alias doorwin -keyalg RSA -keysize 2048 -validity 10950 -storepass %KSPASS% -keypass %KSPASS% -dname "CN=DoorWin,O=DoorWin,C=CN"

echo [6/6] Signing...
"%BT%\apksigner.bat" sign --ks doorwin.keystore --ks-pass pass:%KSPASS% --key-pass pass:%KSPASS% --out doorwin.apk build\aligned.apk
if errorlevel 1 goto :err
"%BT%\apksigner.bat" verify doorwin.apk
echo.
echo BUILD OK: %cd%\doorwin.apk
goto :eof

:err
echo BUILD FAILED
exit /b 1
