@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Bitte zuerst setup.bat ausfuehren.
  pause
  exit /b 1
)
if not exist "node_modules\blockly\blockly_compressed.js" (
  echo Blockly fehlt. Bitte zuerst setup.bat ausfuehren.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" app.py
if errorlevel 1 pause

