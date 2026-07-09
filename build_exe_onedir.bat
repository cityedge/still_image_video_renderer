@echo off
setlocal
cd /d "%~dp0"

if not exist .venv (
  py -3.10 -m venv .venv
)

set "PYTHON=%CD%\.venv\Scripts\python.exe"
set "PSRUN=powershell -NoProfile -ExecutionPolicy Bypass -Command"

%PSRUN% "& '%PYTHON%' -m pip install --upgrade pip"
if errorlevel 1 exit /b 1
%PSRUN% "& '%PYTHON%' -m pip install -r requirements.txt pyinstaller"
if errorlevel 1 exit /b 1

%PSRUN% "& '%PYTHON%' -m PyInstaller --noconfirm --clean --windowed --onedir --name StillImageVideoRenderer --collect-all tkinterdnd2 --hidden-import tkinterdnd2.TkinterDnD --add-data 'presets_default.json;.' subtitle_image_mp4_maker.py"
if errorlevel 1 exit /b 1

rem Equivalent PyInstaller command:
rem "%PYTHON%" -m PyInstaller ^
rem   --noconfirm ^
rem   --clean ^
rem   --windowed ^
rem   --onedir ^
rem   --name StillImageVideoRenderer ^
rem   --collect-all tkinterdnd2 ^
rem   --hidden-import tkinterdnd2.TkinterDnD ^
rem   --add-data "presets_default.json;." ^
rem   subtitle_image_mp4_maker.py
rem if errorlevel 1 exit /b 1

if not exist dist\StillImageVideoRenderer\bin mkdir dist\StillImageVideoRenderer\bin
if exist bin\ffmpeg.exe copy /Y bin\ffmpeg.exe dist\StillImageVideoRenderer\bin\ffmpeg.exe
if exist bin\ffprobe.exe copy /Y bin\ffprobe.exe dist\StillImageVideoRenderer\bin\ffprobe.exe
if exist presets.json copy /Y presets.json dist\StillImageVideoRenderer\presets.json
if exist presets_default.json copy /Y presets_default.json dist\StillImageVideoRenderer\presets_default.json
if exist README.md copy /Y README.md dist\StillImageVideoRenderer\README.md
if exist README_ja.txt copy /Y README_ja.txt dist\StillImageVideoRenderer\README_ja.txt
if exist USER_GUIDE.md copy /Y USER_GUIDE.md dist\StillImageVideoRenderer\USER_GUIDE.md
if exist SPECIFICATION_ja.md copy /Y SPECIFICATION_ja.md dist\StillImageVideoRenderer\SPECIFICATION_ja.md
if exist CHANGELOG.md copy /Y CHANGELOG.md dist\StillImageVideoRenderer\CHANGELOG.md
if exist LICENSE copy /Y LICENSE dist\StillImageVideoRenderer\LICENSE

echo.
echo Build finished.
echo Put ffmpeg.exe and ffprobe.exe in dist\StillImageVideoRenderer\bin if they were not copied.
pause
