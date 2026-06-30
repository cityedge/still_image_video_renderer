# AGENTS.md

## Project

This is a Windows Python desktop application project.

## Python environment

- Always use `.venv\Scripts\python.exe`.
- Do not use global Python.
- Do not use ComfyUI's Python.
- Do not use another project's virtual environment.
- Before running Python commands, check:
  - `where python`
  - `.venv\Scripts\python.exe --version`

## Working directory

- Treat this folder as the project root.
- Do not write files to Documents, OneDrive, Desktop, or the user home folder.
- Generated files must go under:
  - `output/`
  - `build/`
  - `dist/`
  - `tests/tmp/`
  - other folders made by app. (ex. final_composer.py)

## Safety

- Do not directly modify input media files.
- Use copies under `tests/tmp/` when testing destructive or conversion behavior.
- Before making changes, run `git status`.
- If there are uncommitted user changes, report them before editing.
- After changes, report changed files and test results.
