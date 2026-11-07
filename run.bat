@echo off
title OmniTradePro Desktop
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    start "" ".venv\Scripts\python.exe" main.py
) else (
    echo Virtual environment missing. Running setup...
    call setup.bat
    start "" ".venv\Scripts\python.exe" main.py
)
exit

