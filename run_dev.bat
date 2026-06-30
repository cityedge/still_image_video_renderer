@echo off
setlocal
cd /d "%~dp0"
if not exist .venv (
  py -3.10 -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt
python subtitle_image_mp4_maker.py
