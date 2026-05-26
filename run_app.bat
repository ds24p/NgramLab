@echo off
REM Run the Shiny app using the active Python on PATH
cd /d "%~dp0"
python -m shiny run --port 50817 "%~dp0app.py"
