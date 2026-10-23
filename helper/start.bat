@echo off
setlocal
cd /d "%~dp0"
set "BIN=%~dp0bin"
set "PY=%~dp0.venv\Scripts\python.exe"
set "LOG=%~dp0start.log"
set "FF_URL=https://github.com/yt-dlp/FFmpeg-Builds/releases/latest/download/ffmpeg-master-latest-win64-gpl.zip"
set "DENO_URL=https://github.com/denoland/deno/releases/latest/download/deno-x86_64-pc-windows-msvc.zip"
if not exist "%BIN%" mkdir "%BIN%"
echo [%date% %time%] start.bat launched >> "%LOG%"

rem --- Register ytdl:// link first, every run (lets the Download button start this helper)
reg add "HKCU\Software\Classes\ytdl" /ve /d "URL:YT Local Downloader" /f >nul
reg add "HKCU\Software\Classes\ytdl" /v "URL Protocol" /d "" /f >nul
reg add "HKCU\Software\Classes\ytdl\shell\open\command" /ve /d "cmd.exe /k \"\"%~dp0start.bat\"\"" /f >nul
echo Link ytdl:// registered.

netstat -ano | findstr /R /C:":9477 .*LISTENING" >nul
if errorlevel 1 goto not_running
echo Helper is already running.
echo [%date% %time%] helper already running >> "%LOG%"
timeout /t 3 >nul
exit /b 0
:not_running

echo [1/5] Checking Python...
where python >nul 2>&1
if not errorlevel 1 goto py_ok
echo     Python not found. Installing with winget...
echo [%date% %time%] python missing >> "%LOG%"
winget install -e --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
if errorlevel 1 echo     winget failed. Install Python manually from python.org ^(tick "Add to PATH"^).
echo     Close this window and run start.bat again.
pause
exit /b 1
:py_ok
echo     OK

echo [2/5] Checking virtual environment...
if exist "%PY%" goto venv_ok
echo     Creating...
python -m venv .venv
:venv_ok
echo     OK

echo [3/5] Checking yt-dlp...
"%PY%" -m pip show yt-dlp >nul 2>&1
if not errorlevel 1 goto ytdlp_ok
echo     Installing yt-dlp...
"%PY%" -m pip install -q "yt-dlp[default]"
:ytdlp_ok
if /i "%~1"=="update" (
  echo     Updating yt-dlp...
  "%PY%" -m pip install -q -U "yt-dlp[default]"
)
echo     OK

echo [4/5] Checking ffmpeg...
if exist "%BIN%\ffmpeg.exe" if exist "%BIN%\ffprobe.exe" goto ff_ok
echo     Downloading ffmpeg ^(one time, ~150 MB^)...
powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest '%FF_URL%' -OutFile '%TEMP%\ff.zip'; Expand-Archive '%TEMP%\ff.zip' '%TEMP%\ff' -Force; Get-ChildItem '%TEMP%\ff' -Recurse -Include ffmpeg.exe,ffprobe.exe | Copy-Item -Destination '%BIN%' -Force; Remove-Item '%TEMP%\ff.zip','%TEMP%\ff' -Recurse -Force"
:ff_ok
echo     OK

echo [5/5] Checking deno...
if exist "%BIN%\deno.exe" goto deno_ok
echo     Downloading deno ^(one time^)...
powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest '%DENO_URL%' -OutFile '%TEMP%\deno.zip'; Expand-Archive '%TEMP%\deno.zip' '%TEMP%\deno' -Force; Copy-Item '%TEMP%\deno\deno.exe' '%BIN%' -Force; Remove-Item '%TEMP%\deno.zip','%TEMP%\deno' -Recurse -Force"
:deno_ok
echo     OK

echo.
echo Starting helper. Keep this window open.
echo [%date% %time%] starting server >> "%LOG%"
"%PY%" server.py
echo [%date% %time%] server exited with code %errorlevel% >> "%LOG%"
pause
