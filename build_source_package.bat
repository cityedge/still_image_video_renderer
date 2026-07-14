@echo off
setlocal
cd /d "%~dp0"

set "VERSION=1.1.0"
set "PACKAGE_NAME=StillImageVideoRenderer_source_v%VERSION%"
set "STAGING=dist\%PACKAGE_NAME%"
set "ARCHIVE=dist\%PACKAGE_NAME%.zip"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$root = (Resolve-Path -LiteralPath '.').Path; " ^
  "$stage = Join-Path $root '%STAGING%'; " ^
  "$archive = Join-Path $root '%ARCHIVE%'; " ^
  "if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }; " ^
  "if (Test-Path -LiteralPath $archive) { Remove-Item -LiteralPath $archive -Force }; " ^
  "New-Item -ItemType Directory -Path $stage -Force | Out-Null; " ^
  "$files = @('subtitle_image_mp4_maker.py','presets_default.json','requirements.txt','run_dev.bat','make_venv.bat','build_exe_onedir.bat','build_source_package.bat','README.md','README_ja.txt','USER_GUIDE.md','SPECIFICATION_ja.md','CHANGELOG.md','LICENSE','docs\original_batch_presets.txt'); " ^
  "foreach ($relative in $files) { $source = Join-Path $root $relative; if (-not (Test-Path -LiteralPath $source)) { throw ('Missing release file: ' + $relative) }; $destination = Join-Path $stage $relative; New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null; Copy-Item -LiteralPath $source -Destination $destination -Force }; " ^
  "Compress-Archive -LiteralPath $stage -DestinationPath $archive -Force"
if errorlevel 1 exit /b 1

echo.
echo Created %ARCHIVE%
