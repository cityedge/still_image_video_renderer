# Still Image Video Renderer

Still Image Video Renderer is a Windows-oriented Python/Tkinter app that creates MP4 videos from a still image, an audio file, and an optional SRT subtitle file.

The app is an ffmpeg / ffprobe wrapper. It is designed to replace batch-file workflows where audio is first normalized to WAV, measured with ffprobe, and then used as the exact duration for a still-image MP4 render.

Current version: `1.1.0`

## Main Features

- Create an MP4 from a still image and MP3/WAV audio.
- Burn SRT subtitles into the video when an SRT file is provided.
- Create subtitle-free MP4s when no SRT file is provided.
- Add up to two lines of title text and up to two native-size PNG/JPEG icons to the still image before rendering.
- Control title font, bold, italic, color, outline, shadow, X/Y position, line gap, and second-line indent.
- Auto-detect same-name audio files and `<SRT stem>_title.png` when an SRT file is loaded.
- Use quick preset panels for drag-and-drop workflows.
- Continue preparing and starting additional MP4 jobs while ffmpeg is already rendering another job.
- Preview with a fast approximate Pillow/Tkinter preview and an accurate ffmpeg render preview.
- Generate a render preview at startup and after image, audio, or SRT selection.
- Switch the main UI between Japanese and English.
- Store preset names and quick panel labels separately for Japanese and English, with fallback to the other language when one side is not set.
- Load the bundled `presets_default.json` as the default preset layout.
- Prevent black ffmpeg / ffprobe console windows on Windows subprocess launches.

## Requirements

- Windows
- Python 3.10 or later
- ffmpeg and ffprobe
- Python packages listed in `requirements.txt`

Install dependencies:

```bat
py -3.10 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run

```bat
run_dev.bat
```

or:

```bat
.venv\Scripts\python.exe subtitle_image_mp4_maker.py
```

## ffmpeg / ffprobe

The app searches for `ffmpeg.exe` and `ffprobe.exe` in this order:

1. `bin/ffmpeg.exe` and `bin/ffprobe.exe`
2. `ffmpeg.exe` and `ffprobe.exe` next to the app script
3. `PATH`

The GitHub source package does not include ffmpeg binaries. Put local copies under `bin/` or install ffmpeg separately and add it to `PATH`.

## Documentation

- [User Guide](USER_GUIDE.md)
- [Japanese README](README_ja.txt)
- [Specification Memo](SPECIFICATION_ja.md)
- [Changelog](CHANGELOG.md)
- [License](LICENSE)

## Build Notes

`build_exe_onedir.bat` is provided for PyInstaller onedir builds. It uses `presets_default.json` and does not copy a local `presets.json` into the distribution.

To create the GitHub source archive without running PyInstaller:

```bat
build_source_package.bat
```

The result is `dist\StillImageVideoRenderer_source_v1.1.0.zip`. It excludes ffmpeg binaries, local presets, virtual environments, and build artifacts.

## License

MIT License. See [LICENSE](LICENSE).
