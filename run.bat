@echo off
cd /d "%~dp0"

:: Default ASGI module (change to your app module: e.g. mypkg.app:app)
if "%APP_MODULE%"=="" set APP_MODULE=ppt_agent.app:app
if "%PORT%"=="" set PORT=8000
:: If you prefer to use the project's `adk` CLI, leave USE_ADK=1 (default). Set to 0 to force uvicorn.
if "%USE_ADK%"=="" set USE_ADK=1

:: Create venv if needed
if exist .venv (
    call .venv\Scripts\activate.bat
) else (
    python -m venv .venv
    call .venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    python -m pip install -r ppt_agent\requirements.txt
)

echo Environment: APP_MODULE=%APP_MODULE% PORT=%PORT% USE_ADK=%USE_ADK%

:: If `adk` is available and enabled, prefer it (it may initialize extra environment or tooling your project needs).
where adk >nul 2>nul
if %errorlevel%==0 if "%USE_ADK%"=="1" (
    echo Found "adk" — starting adk web in background
    start "adk-web" /B adk web
) else (
    echo adk not found or disabled; starting uvicorn %APP_MODULE% in background on http://localhost:%PORT%
    start "uvicorn" /B uvicorn %APP_MODULE% --host 0.0.0.0 --port %PORT% --reload
)

:: Try to wait until the server responds (short polling) and then open the default browser.
:: Use PowerShell Invoke-WebRequest in a small loop; this is robust on modern Windows.
powershell -NoProfile -Command "\
$url = 'http://127.0.0.1:%PORT%'; \
for ($i=0; $i -lt 50; $i++) { try { Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 1 | Out-Null; break } catch { Start-Sleep -Milliseconds 100 } } ; \
Start-Process $url\
"

pause