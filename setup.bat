@echo off
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Bitte Python 3.11 oder neuer installieren.
  pause
  exit /b 1
)
where npm.cmd >nul 2>nul
if errorlevel 1 (
  echo Bitte Node.js mit npm installieren.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" python -m venv .venv
if errorlevel 1 goto :failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :failed
call npm.cmd ci --ignore-scripts
if errorlevel 1 goto :failed
echo Fertig! Jetzt start.bat oeffnen.
pause
exit /b 0
:failed
echo Installation fehlgeschlagen. Bitte die Meldung oben pruefen.
pause
exit /b 1
