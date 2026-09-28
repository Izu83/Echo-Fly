@echo off
rem Opens the Carry-Walk simulation in the default browser. No install needed.
cd /d "%~dp0"
if not exist "web\brain_data.js" (
    echo web\brain_data.js is missing, rebuilding it from the wall-dodge sub-circuit...
    python scripts\export_brain.py || (pause & exit /b 1)
)
start "" "web\index.html"
