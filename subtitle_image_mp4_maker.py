# -*- coding: utf-8 -*-
"""
Still Image Video Renderer
Version 0.2.0

Purpose:
  Create an MP4 video from a still image, an audio file, and an optional SRT subtitle file.
  This is a GUI ffmpeg wrapper with preset panels, drag-and-drop, rendered preview,
  and working-style edits.

Dependencies:
  pip install pillow tkinterdnd2

Distribution note:
  PyInstaller onedir build should include:
    --collect-data tkinterdnd2
"""
from __future__ import annotations

import json
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from tkinter import ttk
import tkinter.font as tkfont

try:
    from PIL import Image, ImageDraw, ImageFont, ImageTk
except Exception as exc:  # pragma: no cover
    raise SystemExit("Pillow is required. Install with: pip install pillow") from exc

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except Exception:
    DND_FILES = None
    TkinterDnD = None
    DND_AVAILABLE = False

APP_TITLE = "Still Image Video Renderer"
APP_VERSION = "0.2.0"
PREVIEW_FONT_SCALE_DEFAULT = 0.76
SETTINGS_VERSION = 4
DEFAULT_PREVIEW_FONT = "Yu Gothic UI"
LANGUAGE_JA = "日本語"
LANGUAGE_EN = "English"
LANGUAGE_CODES = {LANGUAGE_JA: "ja", LANGUAGE_EN: "en", "ja": "ja", "en": "en"}
ASS_PLAY_RES_Y = 288.0
ASS_DEFAULT_FONT_SIZE = 16.0
PREVIEW_PLACEHOLDER_SIZE = (1280, 720)
DEFAULT_PREVIEW_SUBTITLE_JA = "プレビュー用字幕テキスト"
DEFAULT_PREVIEW_SUBTITLE_EN = "Subtitle text for preview"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
AUDIO_EXTS = {".mp3", ".wav"}
SRT_EXTS = {".srt"}

UI_TEXT = {
    "日本語": {
        "language": "言語 / Language",
        "quick_panel": "クイックパネル",
        "page_rename": "ページ名変更",
        "reload": "再読込",
        "panel_hint": "パネルに画像・音源・任意のSRTをドロップ",
        "preview_not_generated": "プレビュー未生成",
        "render_preview": "レンダープレビュー更新",
        "preview_subtitle": "プレビュー字幕:",
        "preview_placeholder_text": DEFAULT_PREVIEW_SUBTITLE_JA,
        "longest_srt": "SRT最長行",
        "generic_drop_title": "汎用ドロップエリア",
        "generic_drop": "画像・音源・任意のSRTをここにドロップ",
        "all_presets": "全プリセット:",
        "apply": "適用",
        "input_files": "入力ファイル",
        "image": "画像",
        "audio": "音源",
        "srt": "SRT",
        "output": "出力",
        "select": "選択",
        "set_output": "指定",
        "current_style": "現在の字幕設定",
        "source_none": "元プリセット: なし",
        "source_prefix": "元プリセット: ",
        "changed": " ※変更あり",
        "font": "フォント名",
        "size": "サイズ",
        "reset_preset": "元プリセットに戻す",
        "reset_preset_short": "プリセット\n戻す",
        "save_new_preset": "新規プリセットとして保存",
        "save_new_preset_short": "プリセット\n新規保存",
        "overwrite_preset": "選択中プリセットに上書き",
        "overwrite_preset_short": "プリセット\n上書き",
        "delete_preset": "選択したプリセットを消去",
        "delete_preset_short": "プリセット\n消去",
        "delete_preset_title": "プリセット消去",
        "delete_preset_none": "消去するプリセットが選択されていません。",
        "delete_preset_confirm": "「{name}」を消去します。よろしいですか？",
        "delete_preset_done": "プリセットを消去: {name}",
        "mp4_section": "動画作成",
        "create_mp4": "MP4作成",
        "jobs": "MP4ジョブ",
        "job_status": "状態",
        "job_output": "出力",
        "log": "ログ",
        "unset": "未選択",
        "unset_output": "未設定",
        "empty_slot": "空き",
        "simple_preview": "簡易プレビュー",
        "simple_preview_placeholder": "簡易プレビュー（白背景）",
        "rendering_preview": "レンダープレビュー生成中...",
        "render_preview_done": "レンダープレビュー",
        "render_preview_failed": "レンダープレビュー失敗",
    },
    "English": {
        "language": "Language / 言語",
        "quick_panel": "Quick Panel",
        "page_rename": "Rename Page",
        "reload": "Reload",
        "panel_hint": "Drop image, audio, and optional SRT onto a panel",
        "preview_not_generated": "No preview",
        "render_preview": "Update Render Preview",
        "preview_subtitle": "Preview subtitle:",
        "preview_placeholder_text": DEFAULT_PREVIEW_SUBTITLE_EN,
        "longest_srt": "Longest SRT line",
        "generic_drop_title": "Generic drop area",
        "generic_drop": "Drop image, audio, and optional SRT here",
        "all_presets": "All presets:",
        "apply": "Apply",
        "input_files": "Input files",
        "image": "Image",
        "audio": "Audio",
        "srt": "SRT",
        "output": "Output",
        "select": "Select",
        "set_output": "Set",
        "current_style": "Current style",
        "source_none": "Source preset: none",
        "source_prefix": "Source preset: ",
        "changed": " *modified",
        "font": "Font",
        "size": "Size",
        "reset_preset": "Reset to preset",
        "reset_preset_short": "Preset\nReset",
        "save_new_preset": "Save as new preset",
        "save_new_preset_short": "Preset\nSave New",
        "overwrite_preset": "Overwrite selected preset",
        "overwrite_preset_short": "Preset\nOverwrite",
        "delete_preset": "Delete selected preset",
        "delete_preset_short": "Preset\nDelete",
        "delete_preset_title": "Delete preset",
        "delete_preset_none": "No preset is selected.",
        "delete_preset_confirm": "Delete \"{name}\"?",
        "delete_preset_done": "Deleted preset: {name}",
        "mp4_section": "Video render",
        "create_mp4": "Create MP4",
        "jobs": "MP4 Jobs",
        "job_status": "Status",
        "job_output": "Output",
        "log": "Log",
        "unset": "Not selected",
        "unset_output": "Not set",
        "empty_slot": "Empty",
        "simple_preview": "Simple preview",
        "simple_preview_placeholder": "Simple preview (white background)",
        "rendering_preview": "Rendering preview...",
        "render_preview_done": "Render preview",
        "render_preview_failed": "Render preview failed",
    },
}

ALIGNMENT_LABELS = {
    "日本語": {6: "6（中央上）", 10: "10（中央）"},
    "English": {6: "6 (Top center)", 10: "10 (Center)"},
}


# -----------------------------
# Path / process helpers
# -----------------------------

def app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def startupinfo_no_window():
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
        return startupinfo
    return None


def creationflags_no_window() -> int:
    if os.name == "nt":
        return getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return 0


def subprocess_no_window_kwargs() -> Dict[str, Any]:
    """Return subprocess kwargs that prevent console windows on Windows."""
    if os.name != "nt":
        return {}
    return {
        "startupinfo": startupinfo_no_window(),
        "creationflags": creationflags_no_window(),
    }


def which_exe(name: str) -> Optional[str]:
    found = shutil.which(name)
    return found


def find_tool(name: str) -> Optional[str]:
    base = app_base_dir()
    candidates = [
        base / "bin" / f"{name}.exe",
        base / "bin" / name,
        base / f"{name}.exe",
        base / name,
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return which_exe(name)


def run_subprocess(cmd: List[str], log_func=None, check=True) -> subprocess.CompletedProcess:
    if log_func:
        log_func("$ " + " ".join(f'"{x}"' if " " in x else x for x in cmd))
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        **subprocess_no_window_kwargs(),
    )
    if log_func:
        if proc.stdout.strip():
            log_func(proc.stdout.strip())
        if proc.stderr.strip():
            log_func(proc.stderr.strip())
    if check and proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"Command failed: {proc.returncode}")
    return proc


def popen_subprocess(cmd: List[str], log_func=None, **kwargs) -> subprocess.Popen:
    """Start a subprocess with the same no-window behavior as run_subprocess."""
    if log_func:
        log_func("$ " + " ".join(f'"{x}"' if " " in x else x for x in cmd))
    process_kwargs = subprocess_no_window_kwargs()
    process_kwargs.update(kwargs)
    return subprocess.Popen(cmd, **process_kwargs)


# -----------------------------
# Presets
# -----------------------------

DEFAULT_PRESETS: Dict[str, Any] = {
    "settings": {
        "preview_font_scale": PREVIEW_FONT_SCALE_DEFAULT,
        "default_preview_font": DEFAULT_PREVIEW_FONT,
    },
    "presets": [
        {
            "id": "normal_top_v0",
            "name": "01 通常 字幕上部 v0",
            "tags": ["normal"],
            "style": {"fontname": "UD デジタル 教科書体 NK", "fontsize": 20, "alignment": 6, "margin_v": None},
        },
        {
            "id": "normal_up2_v45",
            "name": "02 通常 字幕上げ2 v45",
            "tags": ["normal"],
            "style": {"fontname": "UD デジタル 教科書体 NK", "fontsize": 20, "alignment": 6, "margin_v": 45},
        },
        {
            "id": "normal_up_v65",
            "name": "03 通常 字幕上げ v65",
            "tags": ["normal"],
            "style": {"fontname": "UD デジタル 教科書体 NK", "fontsize": 20, "alignment": 6, "margin_v": 65},
        },
        {
            "id": "normal_slightly_up_v95",
            "name": "04 通常 字幕やや上 v95",
            "tags": ["normal"],
            "style": {"fontname": "UD デジタル 教科書体 NK", "fontsize": 20, "alignment": 6, "margin_v": 95},
        },
        {
            "id": "normal_tiny_up_v110",
            "name": "04b 通常 字幕わずか上 v110",
            "tags": ["normal"],
            "style": {"fontname": "UD デジタル 教科書体 NK", "fontsize": 20, "alignment": 6, "margin_v": 110},
        },
        {
            "id": "normal_center_a10",
            "name": "05 通常 字幕センター a10",
            "tags": ["normal"],
            "style": {"fontname": "UD デジタル 教科書体 NK", "fontsize": 20, "alignment": 10, "margin_v": None},
        },
        {
            "id": "normal_slightly_down_v155",
            "name": "06 通常 字幕やや下 v155",
            "tags": ["normal"],
            "style": {"fontname": "UD デジタル 教科書体 NK", "fontsize": 20, "alignment": 6, "margin_v": 155},
        },
        {
            "id": "normal_down_v185",
            "name": "07 通常 字幕下げ v185",
            "tags": ["normal"],
            "style": {"fontname": "UD デジタル 教科書体 NK", "fontsize": 20, "alignment": 6, "margin_v": 185},
        },
        {
            "id": "normal_down2_v215",
            "name": "08 通常 字幕下げ2 v215",
            "tags": ["normal"],
            "style": {"fontname": "UD デジタル 教科書体 NK", "fontsize": 20, "alignment": 6, "margin_v": 215},
        },
        {
            "id": "short_up2_v55",
            "name": "12 ショート 字幕上げ2 v55",
            "tags": ["short"],
            "style": {"fontname": None, "fontsize": None, "alignment": 6, "margin_v": 55},
        },
        {
            "id": "short_up_v80",
            "name": "13 ショート 字幕上げ v80",
            "tags": ["short"],
            "style": {"fontname": None, "fontsize": None, "alignment": 6, "margin_v": 80},
        },
        {
            "id": "short_slightly_up_v90",
            "name": "14 ショート 字幕やや上 v90",
            "tags": ["short"],
            "style": {"fontname": None, "fontsize": None, "alignment": 6, "margin_v": 90},
        },
        {
            "id": "short_tiny_up_v105",
            "name": "14b ショート 字幕わずか上 v105",
            "tags": ["short"],
            "style": {"fontname": None, "fontsize": None, "alignment": 6, "margin_v": 105},
        },
        {
            "id": "short_center_a10",
            "name": "15 ショート 字幕センター a10",
            "tags": ["short"],
            "style": {"fontname": None, "fontsize": None, "alignment": 10, "margin_v": None},
        },
        {
            "id": "short_slightly_down_v155",
            "name": "16 ショート 字幕やや下 v155",
            "tags": ["short"],
            "style": {"fontname": None, "fontsize": None, "alignment": 6, "margin_v": 155},
        },
        {
            "id": "short_down_v185",
            "name": "17 ショート 字幕下げ v185",
            "tags": ["short"],
            "style": {"fontname": None, "fontsize": None, "alignment": 6, "margin_v": 185},
        },
        {
            "id": "short_down2_v215",
            "name": "18 ショート 字幕下げ2 v215",
            "tags": ["short"],
            "style": {"fontname": None, "fontsize": None, "alignment": 6, "margin_v": 215},
        },
    ],
    "panel_pages": [
        {
            "id": "page1",
            "name": "ページ1 / Page 1",
            "rows": 5,
            "cols": 4,
            "slots": [
                {"slot": 1, "preset_id": "normal_top_v0", "label": "上部"},
                {"slot": 2, "preset_id": "normal_up2_v45", "label": "上げ2"},
                {"slot": 3, "preset_id": "normal_up_v65", "label": "上げ"},
                {"slot": 4, "preset_id": "normal_slightly_up_v95", "label": "やや上"},
                {"slot": 5, "preset_id": "normal_tiny_up_v110", "label": "わずか上"},
                {"slot": 6, "preset_id": "normal_center_a10", "label": "センター"},
                {"slot": 7, "preset_id": "normal_slightly_down_v155", "label": "やや下"},
                {"slot": 8, "preset_id": "normal_down_v185", "label": "下げ"},
                {"slot": 9, "preset_id": "normal_down2_v215", "label": "下げ2"},
                {"slot": 13, "preset_id": "short_up2_v55", "label": "S上げ2"},
                {"slot": 14, "preset_id": "short_up_v80", "label": "S上げ"},
                {"slot": 15, "preset_id": "short_slightly_up_v90", "label": "Sやや上"},
                {"slot": 16, "preset_id": "short_tiny_up_v105", "label": "Sわずか上"},
                {"slot": 17, "preset_id": "short_center_a10", "label": "Sセンター"},
                {"slot": 18, "preset_id": "short_slightly_down_v155", "label": "Sやや下"},
                {"slot": 19, "preset_id": "short_down_v185", "label": "S下げ"},
                {"slot": 20, "preset_id": "short_down2_v215", "label": "S下げ2"},
            ],
        },
        {
            "id": "page2",
            "name": "ページ2 / Page 2",
            "rows": 5,
            "cols": 4,
            "slots": [],
        },
    ],
}


PRESET_DISPLAY_DATA: Dict[str, Dict[str, Dict[str, Optional[str]]]] = {
    "normal_top_v0": {
        "name": {"ja": "01 通常 字幕上部 v0", "en": "01 Normal Top v0"},
        "label": {"ja": "上部", "en": "Top"},
    },
    "normal_up2_v45": {
        "name": {"ja": "02 通常 字幕上げ2 v45", "en": "02 Normal Up 2 v45"},
        "label": {"ja": "上げ2", "en": "Up 2"},
    },
    "normal_up_v65": {
        "name": {"ja": "03 通常 字幕上げ v65", "en": "03 Normal Up v65"},
        "label": {"ja": "上げ", "en": "Up"},
    },
    "normal_slightly_up_v95": {
        "name": {"ja": "04 通常 字幕やや上 v95", "en": "04 Normal Slightly Up v95"},
        "label": {"ja": "やや上", "en": "Slight Up"},
    },
    "normal_tiny_up_v110": {
        "name": {"ja": "04b 通常 字幕わずか上 v110", "en": "04b Normal Tiny Up v110"},
        "label": {"ja": "わずか上", "en": "Tiny Up"},
    },
    "normal_center_a10": {
        "name": {"ja": "05 通常 字幕センター a10", "en": "05 Normal Center a10"},
        "label": {"ja": "センター", "en": "Center"},
    },
    "normal_slightly_down_v155": {
        "name": {"ja": "06 通常 字幕やや下 v155", "en": "06 Normal Slightly Down v155"},
        "label": {"ja": "やや下", "en": "Slight Down"},
    },
    "normal_down_v185": {
        "name": {"ja": "07 通常 字幕下げ v185", "en": "07 Normal Down v185"},
        "label": {"ja": "下げ", "en": "Down"},
    },
    "normal_down2_v215": {
        "name": {"ja": "08 通常 字幕下げ2 v215", "en": "08 Normal Down 2 v215"},
        "label": {"ja": "下げ2", "en": "Down 2"},
    },
    "short_up2_v55": {
        "name": {"ja": "12 ショート 字幕上げ2 v55", "en": "12 Short Up 2 v55"},
        "label": {"ja": "S上げ2", "en": "S Up 2"},
    },
    "short_up_v80": {
        "name": {"ja": "13 ショート 字幕上げ v80", "en": "13 Short Up v80"},
        "label": {"ja": "S上げ", "en": "S Up"},
    },
    "short_slightly_up_v90": {
        "name": {"ja": "14 ショート 字幕やや上 v90", "en": "14 Short Slightly Up v90"},
        "label": {"ja": "Sやや上", "en": "S Slight Up"},
    },
    "short_tiny_up_v105": {
        "name": {"ja": "14b ショート 字幕わずか上 v105", "en": "14b Short Tiny Up v105"},
        "label": {"ja": "Sわずか上", "en": "S Tiny Up"},
    },
    "short_center_a10": {
        "name": {"ja": "15 ショート 字幕センター a10", "en": "15 Short Center a10"},
        "label": {"ja": "Sセンター", "en": "S Center"},
    },
    "short_slightly_down_v155": {
        "name": {"ja": "16 ショート 字幕やや下 v155", "en": "16 Short Slightly Down v155"},
        "label": {"ja": "Sやや下", "en": "S Slight Down"},
    },
    "short_down_v185": {
        "name": {"ja": "17 ショート 字幕下げ v185", "en": "17 Short Down v185"},
        "label": {"ja": "S下げ", "en": "S Down"},
    },
    "short_down2_v215": {
        "name": {"ja": "18 ショート 字幕下げ2 v215", "en": "18 Short Down 2 v215"},
        "label": {"ja": "S下げ2", "en": "S Down 2"},
    },
}

PAGE_DISPLAY_DATA: Dict[str, Dict[str, Optional[str]]] = {
    "page1": {"ja": "ページ1", "en": "Page 1"},
    "page2": {"ja": "ページ2", "en": "Page 2"},
}


def normalize_language_code(language: str) -> str:
    return LANGUAGE_CODES.get(language, "ja")


def localized_text(value: Any, language: str, fallback: str = "") -> str:
    if value is None:
        return fallback
    if isinstance(value, dict):
        code = normalize_language_code(language)
        other = "en" if code == "ja" else "ja"
        for key in (code, other):
            text = value.get(key)
            if text:
                return str(text)
        for text in value.values():
            if text:
                return str(text)
        return fallback
    text = str(value)
    return text if text else fallback


def localized_record(text: str, language: str, existing: Any = None) -> Dict[str, Optional[str]]:
    code = normalize_language_code(language)
    other = "en" if code == "ja" else "ja"
    record: Dict[str, Optional[str]] = {"ja": None, "en": None}
    if isinstance(existing, dict):
        record["ja"] = existing.get("ja")
        record["en"] = existing.get("en")
    elif existing:
        record[other] = str(existing)
    record[code] = text
    return record


def apply_default_preset_display_data(data: Dict[str, Any]):
    for preset in data.get("presets", []):
        display = PRESET_DISPLAY_DATA.get(preset.get("id"))
        if display:
            preset["name"] = display["name"]
    for page in data.get("panel_pages", []):
        page_name = PAGE_DISPLAY_DATA.get(page.get("id"))
        if page_name:
            page["name"] = page_name
        for slot in page.get("slots", []):
            display = PRESET_DISPLAY_DATA.get(slot.get("preset_id"))
            if display:
                slot["label"] = display["label"]


apply_default_preset_display_data(DEFAULT_PRESETS)


@dataclass
class Preset:
    id: str
    name: Any
    style: Dict[str, Any]
    tags: List[str] = field(default_factory=list)


@dataclass
class VideoJob:
    id: str
    image_path: str
    audio_path: str
    srt_path: Optional[str]
    output_path: str
    style: Dict[str, Any]
    created_at: str
    status: str = "queued"
    error: Optional[str] = None
    thread: Optional[threading.Thread] = field(default=None, repr=False, compare=False)

    @property
    def short_id(self) -> str:
        return self.id[:8]


class PresetStore:
    def __init__(self, path: Path):
        self.path = path
        self.data: Dict[str, Any] = {}
        self.load()

    def migrate(self):
        settings = self.settings()
        version = int(settings.get("settings_version", 0) or 0)
        # Prototype preset data can be reset because this app is not public yet.
        if version < 4:
            self.data = json.loads(json.dumps(DEFAULT_PRESETS, ensure_ascii=False))
            self.data.setdefault("settings", {})["settings_version"] = SETTINGS_VERSION
            self.save()
            return
        if version < SETTINGS_VERSION:
            settings["preview_font_scale"] = PREVIEW_FONT_SCALE_DEFAULT
            settings.setdefault("default_preview_font", DEFAULT_PREVIEW_FONT)
            settings["settings_version"] = SETTINGS_VERSION
            self.save()

    def migrate_panel_layout_v3(self):
        default_pages = json.loads(json.dumps(DEFAULT_PRESETS["panel_pages"], ensure_ascii=False))
        default_ids = {
            slot.get("preset_id")
            for page in DEFAULT_PRESETS["panel_pages"]
            for slot in page.get("slots", [])
            if slot.get("preset_id")
        }
        custom_slots = []
        for page in self.panel_pages:
            for slot in page.get("slots", []):
                preset_id = slot.get("preset_id")
                if preset_id and preset_id not in default_ids:
                    custom_slots.append(dict(slot))
        page2 = default_pages[1]
        used = {int(slot.get("slot", 0)) for slot in page2.get("slots", [])}
        next_slot = 1
        for slot in custom_slots:
            while next_slot in used and next_slot <= int(page2.get("rows", 5)) * int(page2.get("cols", 4)):
                next_slot += 1
            if next_slot > int(page2.get("rows", 5)) * int(page2.get("cols", 4)):
                break
            slot["slot"] = next_slot
            page2.setdefault("slots", []).append(slot)
            used.add(next_slot)
            next_slot += 1
        self.data["panel_pages"] = default_pages

    def load(self):
        if self.path.exists():
            with self.path.open("r", encoding="utf-8") as f:
                self.data = json.load(f)
            self.migrate()
        else:
            self.data = json.loads(json.dumps(DEFAULT_PRESETS, ensure_ascii=False))
            self.data.setdefault("settings", {})["settings_version"] = SETTINGS_VERSION
            self.save()

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    @property
    def presets(self) -> List[Dict[str, Any]]:
        return self.data.setdefault("presets", [])

    @property
    def panel_pages(self) -> List[Dict[str, Any]]:
        return self.data.setdefault("panel_pages", [])

    def settings(self) -> Dict[str, Any]:
        return self.data.setdefault("settings", {})

    def preset_by_id(self, preset_id: str) -> Optional[Dict[str, Any]]:
        for p in self.presets:
            if p.get("id") == preset_id:
                return p
        return None

    def preset_name_map(self, language: str = "ja") -> Dict[str, str]:
        return {localized_text(p.get("name"), language, p.get("id", "")): p.get("id", "") for p in self.presets}

    def add_preset(self, name: str, style: Dict[str, Any], tags: Optional[List[str]] = None, language: str = "ja") -> Dict[str, Any]:
        base_id = re.sub(r"[^0-9A-Za-z_]+", "_", name).strip("_") or "preset"
        preset_id = base_id.lower()
        existing = {p.get("id") for p in self.presets}
        if preset_id in existing:
            preset_id = f"{preset_id}_{uuid.uuid4().hex[:6]}"
        preset = {"id": preset_id, "name": localized_record(name, language), "tags": tags or [], "style": style}
        self.presets.append(preset)
        self.save()
        return preset

    def update_preset(self, preset_id: str, style: Dict[str, Any]) -> bool:
        p = self.preset_by_id(preset_id)
        if not p:
            return False
        p["style"] = style
        self.save()
        return True

    def delete_preset(self, preset_id: str) -> bool:
        before = len(self.presets)
        self.data["presets"] = [p for p in self.presets if p.get("id") != preset_id]
        if len(self.presets) == before:
            return False
        for page in self.panel_pages:
            slots = page.setdefault("slots", [])
            slots[:] = [s for s in slots if s.get("preset_id") != preset_id]
        self.save()
        return True

    def first_empty_slot(self, page_index: int) -> Optional[int]:
        if page_index < 0 or page_index >= len(self.panel_pages):
            return None
        page = self.panel_pages[page_index]
        rows = int(page.get("rows", 5))
        cols = int(page.get("cols", 4))
        occupied = {int(s.get("slot", 0)) for s in page.setdefault("slots", [])}
        for i in range(1, rows * cols + 1):
            if i not in occupied:
                return i
        return None

    def assign_to_slot(self, page_index: int, slot: int, preset_id: str, label: Any):
        page = self.panel_pages[page_index]
        slots = page.setdefault("slots", [])
        slots[:] = [s for s in slots if int(s.get("slot", 0)) != slot]
        slots.append({"slot": slot, "preset_id": preset_id, "label": label})
        slots.sort(key=lambda x: int(x.get("slot", 0)))
        self.save()


# -----------------------------
# SRT / subtitle helpers
# -----------------------------

def read_text_guess_encoding(path: str) -> str:
    data = Path(path).read_bytes()
    for enc in ("utf-8-sig", "utf-8", "cp932", "shift_jis"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def normalize_srt_to_utf8(src: str, dst: str):
    text = read_text_guess_encoding(src)
    Path(dst).write_text(text, encoding="utf-8")


def srt_preview_text(path: Optional[str], fallback: str = DEFAULT_PREVIEW_SUBTITLE_JA) -> str:
    if not path or not Path(path).exists():
        return fallback
    try:
        text = read_text_guess_encoding(path)
    except Exception:
        return fallback
    blocks = re.split(r"\n\s*\n", text.replace("\r\n", "\n").replace("\r", "\n"))
    candidates: List[str] = []
    for block in blocks:
        lines = [ln.strip() for ln in block.split("\n")]
        useful = []
        for ln in lines:
            if not ln:
                continue
            if re.fullmatch(r"\d+", ln):
                continue
            if "-->" in ln:
                continue
            useful.append(ln)
        if useful:
            candidates.append("\n".join(useful))
    if not candidates:
        return fallback
    return max(candidates, key=lambda s: len(s.replace("\n", "")))


def write_preview_srt(path: str, text: str):
    text = (text or DEFAULT_PREVIEW_SUBTITLE_JA).replace("\r\n", "\n").replace("\r", "\n")
    content = f"1\n00:00:00,000 --> 00:00:10,000\n{text}\n"
    Path(path).write_text(content, encoding="utf-8")


def escape_filter_path(path: str) -> str:
    # FFmpeg subtitles filter path escaping, especially for Windows drive colon.
    p = str(Path(path).resolve()).replace("\\", "/")
    if len(p) >= 2 and p[1] == ":":
        p = p[0] + r"\:" + p[2:]
    p = p.replace("'", r"\'")
    return p


def style_to_force_style(style: Dict[str, Any]) -> str:
    order = [
        ("fontname", "fontname"),
        ("fontsize", "fontsize"),
        ("alignment", "alignment"),
        ("margin_v", "MarginV"),
        ("primary_color", "PrimaryColour"),
        ("outline_color", "OutlineColour"),
        ("outline", "Outline"),
        ("shadow", "Shadow"),
        ("bold", "Bold"),
    ]
    parts = []
    for key, ass_key in order:
        val = style.get(key)
        if val is None or val == "":
            continue
        parts.append(f"{ass_key}={val}")
    return ",".join(parts)


def make_subtitle_filter(srt_path: str, style: Dict[str, Any]) -> str:
    escaped = escape_filter_path(srt_path)
    force_style = style_to_force_style(style)
    if force_style:
        return f"subtitles='{escaped}':force_style='{force_style}'"
    return f"subtitles='{escaped}'"


# -----------------------------
# File classification
# -----------------------------

def classify_paths(paths: List[str]) -> Tuple[List[str], List[str], List[str], List[str]]:
    images, audios, srts, others = [], [], [], []
    for p in paths:
        ext = Path(p).suffix.lower()
        if ext in IMAGE_EXTS:
            images.append(p)
        elif ext in AUDIO_EXTS:
            audios.append(p)
        elif ext in SRT_EXTS:
            srts.append(p)
        else:
            others.append(p)
    return images, audios, srts, others


def sibling_srt_for_audio(audio_path: str) -> Optional[str]:
    p = Path(audio_path)
    candidate = p.with_suffix(".srt")
    if candidate.exists():
        return str(candidate)
    # Case-insensitive fallback on Windows-like folders.
    try:
        for child in p.parent.iterdir():
            if child.is_file() and child.suffix.lower() == ".srt" and child.stem.lower() == p.stem.lower():
                return str(child)
    except Exception:
        pass
    return None


def sibling_title_image_for_audio(audio_path: str) -> Optional[str]:
    """Return <audio-stem>_title.png next to the audio file, with a case-insensitive fallback."""
    p = Path(audio_path)
    candidate = p.with_name(p.stem + "_title.png")
    if candidate.exists():
        return str(candidate)
    target_stem = (p.stem + "_title").lower()
    try:
        for child in p.parent.iterdir():
            if child.is_file() and child.suffix.lower() == ".png" and child.stem.lower() == target_stem:
                return str(child)
    except Exception:
        pass
    return None


def unique_path(path: Path) -> Path:
    """Return path if free, otherwise append _001, _002, ... before the extension."""
    if not path.exists():
        return path
    for i in range(1, 1000):
        candidate = path.with_name(f"{path.stem}_{i:03d}{path.suffix}")
        if not candidate.exists():
            return candidate
    return path.with_name(f"{path.stem}_{uuid.uuid4().hex[:6]}{path.suffix}")


def unique_available_path(path: Path, reserved_paths: set[str]) -> Path:
    """Return a path that is free on disk and not already reserved by a running job."""
    reserved = {str(Path(p).resolve()).lower() for p in reserved_paths}
    if not path.exists() and str(path.resolve()).lower() not in reserved:
        return path
    for i in range(1, 1000):
        candidate = path.with_name(f"{path.stem}_{i:03d}{path.suffix}")
        if not candidate.exists() and str(candidate.resolve()).lower() not in reserved:
            return candidate
    return path.with_name(f"{path.stem}_{uuid.uuid4().hex[:6]}{path.suffix}")


# -----------------------------
# Font helpers for simple preview
# -----------------------------

def windows_fonts_dir() -> Path:
    return Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"


def find_font_file(fontname: Optional[str]) -> Optional[str]:
    # This is intentionally approximate. Render preview is authoritative.
    fonts_dir = windows_fonts_dir()
    candidates: List[str] = []
    if fontname:
        lower = fontname.lower()
        if "ud" in lower and "教科書" in fontname:
            candidates += ["UDDigiKyokashoN-R.ttc", "UDDigiKyokashoNK-R.ttc", "UDDigiKyokashoNP-R.ttc"]
        if "meiryo" in lower or "メイリオ" in fontname:
            candidates += ["meiryo.ttc", "meiryob.ttc"]
        if "yu gothic" in lower or "游ゴシック" in fontname:
            candidates += ["YuGothM.ttc", "YuGothR.ttc", "YuGothB.ttc"]
    candidates += ["meiryo.ttc", "YuGothM.ttc", "YuGothR.ttc", "msgothic.ttc", "arial.ttf"]
    for name in candidates:
        path = fonts_dir / name
        if path.exists():
            return str(path)
    # Linux fallback for sandbox/local non-Windows.
    for path in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    ]:
        if Path(path).exists():
            return path
    return None


def load_preview_font(fontname: Optional[str], size: int):
    path = find_font_file(fontname)
    if path:
        try:
            return ImageFont.truetype(path, max(1, int(size)))
        except Exception:
            pass
    return ImageFont.load_default()


class ToolTip:
    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = text
        self.tip = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, _event=None):
        if self.tip or not self.text:
            return
        x = self.widget.winfo_rootx() + 16
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            self.tip,
            text=self.text,
            bg="#f2f2dc",
            fg="#111111",
            relief=tk.SOLID,
            borderwidth=1,
            padx=6,
            pady=3,
        )
        label.pack()

    def hide(self, _event=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


# -----------------------------
# GUI
# -----------------------------

class App:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_TITLE} {APP_VERSION}")
        self.base = app_base_dir()
        self.store = PresetStore(self.base / "presets.json")

        self.ffmpeg = find_tool("ffmpeg")
        self.ffprobe = find_tool("ffprobe")

        self.image_path: Optional[str] = None
        self.audio_path: Optional[str] = None
        self.srt_path: Optional[str] = None
        self.output_path: Optional[str] = None
        self.output_user_selected = False
        self.current_preset_id: Optional[str] = None
        self.working_style: Dict[str, Any] = {}
        self.dirty = False
        self.current_page_index = 0
        self.render_preview_path: Optional[str] = None
        self.preview_photo = None
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.ui_queue: queue.Queue[Callable[[], None]] = queue.Queue()
        self.pending_logs: List[str] = []
        self.render_thread: Optional[threading.Thread] = None
        self.video_jobs: Dict[str, VideoJob] = {}
        self.job_lock = threading.Lock()
        self.reserved_output_paths: set[str] = set()
        self._suppress_var_events = False
        self.language_var = tk.StringVar(value="日本語")
        self.image_var = tk.StringVar(value=self.tr("unset"))
        self.audio_var = tk.StringVar(value=self.tr("unset"))
        self.srt_var = tk.StringVar(value=self.tr("unset"))
        self.output_var = tk.StringVar(value=self.tr("unset_output"))
        self.i18n_widgets: List[Tuple[Any, str, str]] = []
        self.file_row_labels: Dict[str, Any] = {}

        self.setup_style()
        self.build_ui()
        self.refresh_all_preset_combo()
        self.render_panel()
        self.update_status()
        self.root.after(100, self.process_log_queue)

        if not DND_AVAILABLE:
            self.log("tkinterdnd2 が見つかりません。ドラッグ＆ドロップなしで起動しました。")
            self.log("pip install tkinterdnd2 で有効化できます。")
        if not self.ffmpeg or not self.ffprobe:
            self.log("ffmpeg または ffprobe が見つかりません。bin フォルダまたは PATH を確認してください。")
        else:
            self.log(f"ffmpeg: {self.ffmpeg}")
            self.log(f"ffprobe: {self.ffprobe}")

    def tr(self, key: str) -> str:
        language = self.language_var.get() if hasattr(self, "language_var") else "日本語"
        return UI_TEXT.get(language, UI_TEXT["日本語"]).get(key, key)

    def language_code(self) -> str:
        language = self.language_var.get() if hasattr(self, "language_var") else LANGUAGE_JA
        return normalize_language_code(language)

    def preset_display_name(self, preset: Dict[str, Any]) -> str:
        return localized_text(preset.get("name"), self.language_code(), preset.get("id", "?"))

    def page_display_name(self, page: Dict[str, Any], index: int) -> str:
        return localized_text(page.get("name"), self.language_code(), f"Page {index + 1}")

    def slot_display_label(self, slot: Dict[str, Any]) -> str:
        preset_id = slot.get("preset_id")
        return localized_text(slot.get("label"), self.language_code(), self.label_for_preset(preset_id))

    def register_i18n(self, widget, key: str, option: str = "text"):
        self.i18n_widgets.append((widget, key, option))
        try:
            widget.configure(**{option: self.tr(key)})
        except Exception:
            pass
        return widget

    def on_language_changed(self, *_args):
        for widget, key, option in self.i18n_widgets:
            try:
                widget.configure(**{option: self.tr(key)})
            except Exception:
                pass
        self.refresh_alignment_options()
        self.refresh_preview_placeholder_text()
        self.refresh_all_preset_combo()
        if self.current_preset_id and hasattr(self, "preset_combo_var"):
            preset = self.store.preset_by_id(self.current_preset_id)
            if preset:
                self.preset_combo_var.set(self.preset_display_name(preset))
        if hasattr(self, "jobs_tree"):
            self.jobs_tree.heading("status", text=self.tr("job_status"))
            self.jobs_tree.heading("output", text=self.tr("job_output"))
        self.refresh_file_labels()
        self.update_status()
        self.render_panel()

    def preview_placeholder_values(self) -> set[str]:
        return {DEFAULT_PREVIEW_SUBTITLE_JA, DEFAULT_PREVIEW_SUBTITLE_EN}

    def preview_placeholder_text(self) -> str:
        return self.tr("preview_placeholder_text")

    def refresh_preview_placeholder_text(self):
        if not hasattr(self, "preview_text_var"):
            return
        current = self.preview_text_var.get()
        if not self.srt_path and current in self.preview_placeholder_values():
            self.preview_text_var.set(self.preview_placeholder_text())

    def alignment_values(self) -> List[str]:
        labels = ALIGNMENT_LABELS.get(self.language_var.get(), ALIGNMENT_LABELS["日本語"])
        return [labels[6], labels[10]]

    def format_alignment(self, value: Optional[int]) -> str:
        labels = ALIGNMENT_LABELS.get(self.language_var.get(), ALIGNMENT_LABELS["日本語"])
        return labels.get(value or 6, labels[6])

    def refresh_alignment_options(self):
        if not hasattr(self, "alignment_combo"):
            return
        current = self.parse_int(self.alignment_var.get()) or 6
        self.alignment_combo["values"] = self.alignment_values()
        self.alignment_var.set(self.format_alignment(current))

    def refresh_file_labels(self):
        if hasattr(self, "image_var") and not self.image_path:
            self.image_var.set(self.tr("unset"))
        if hasattr(self, "audio_var") and not self.audio_path:
            self.audio_var.set(self.tr("unset"))
        if hasattr(self, "srt_var") and not self.srt_path:
            self.srt_var.set(self.tr("unset"))
        if hasattr(self, "output_var") and not self.output_path:
            self.output_var.set(self.tr("unset_output"))

    def setup_style(self):
        self.bg = "#1e1f22"
        self.panel_bg = "#2b2d31"
        self.fg = "#eeeeee"
        self.muted = "#b8b8b8"
        self.accent = "#4f83cc"
        self.root.configure(bg=self.bg)
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TFrame", background=self.bg)
        style.configure("Panel.TFrame", background=self.panel_bg)
        style.configure("TLabel", background=self.bg, foreground=self.fg)
        style.configure("Panel.TLabel", background=self.panel_bg, foreground=self.fg)
        style.configure("Panel.TLabelframe", background=self.panel_bg, foreground=self.fg)
        style.configure("Panel.TLabelframe.Label", background=self.panel_bg, foreground=self.fg)
        style.configure("TButton", padding=4)
        style.configure("PresetAction.TButton", padding=[4, 8])
        style.configure("TCheckbutton", background=self.bg, foreground=self.fg)
        style.map("TCheckbutton", background=[("active", self.bg)], foreground=[("active", self.fg)])
        style.configure("TNotebook", background=self.bg)
        style.configure("TNotebook.Tab", padding=[10, 4])
        style.configure("TEntry", fieldbackground="#111214", foreground=self.fg)
        style.configure(
            "Readable.TCombobox",
            fieldbackground="#f2f0ea",
            background="#d8d6d0",
            foreground="#111111",
            arrowcolor="#111111",
        )
        style.map(
            "Readable.TCombobox",
            fieldbackground=[("readonly", "#f2f0ea"), ("focus", "#ffffff")],
            foreground=[("readonly", "#111111"), ("focus", "#111111"), ("disabled", "#777777")],
            selectbackground=[("focus", self.accent)],
            selectforeground=[("focus", "#ffffff")],
        )
        self.root.option_add("*TCombobox*Listbox.background", "#f2f0ea")
        self.root.option_add("*TCombobox*Listbox.foreground", "#111111")
        self.root.option_add("*TCombobox*Listbox.selectBackground", self.accent)
        self.root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

    def build_ui(self):
        main = ttk.Frame(self.root)
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Top area: left quick panel, center preview, right controls
        top = ttk.Frame(main)
        top.pack(fill=tk.BOTH, expand=True)

        self.left = ttk.Frame(top, style="Panel.TFrame")
        self.left.pack(side=tk.LEFT, fill=tk.Y)

        self.right = ttk.Frame(top, style="Panel.TFrame")
        self.right.pack(side=tk.RIGHT, fill=tk.Y)

        self.center = ttk.Frame(top)
        self.center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 8))

        self.build_left_panel()
        self.build_center_preview()
        self.build_right_controls()
        self.build_bottom(main)

    def build_left_panel(self):
        header = ttk.Frame(self.left, style="Panel.TFrame")
        header.pack(fill=tk.X, padx=8, pady=(8, 4))
        self.quick_panel_label = self.register_i18n(ttk.Label(header, style="Panel.TLabel"), "quick_panel")
        self.quick_panel_label.pack(anchor=tk.W)
        tabs = ttk.Frame(self.left, style="Panel.TFrame")
        tabs.pack(fill=tk.X, padx=8, pady=4)
        self.page_buttons: List[tk.Button] = []
        for i in range(2):
            btn = tk.Button(tabs, text=f"ページ{i+1}", command=lambda idx=i: self.set_page(idx), bg="#3a3d44", fg=self.fg,
                            activebackground="#4a4d55", activeforeground=self.fg, relief=tk.FLAT)
            btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
            self.page_buttons.append(btn)
        name_frame = ttk.Frame(self.left, style="Panel.TFrame")
        name_frame.pack(fill=tk.X, padx=8, pady=(0, 6))
        self.page_rename_button = self.register_i18n(ttk.Button(name_frame, command=self.rename_page), "page_rename")
        self.page_rename_button.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.reload_button = self.register_i18n(ttk.Button(name_frame, command=self.reload_presets), "reload")
        self.reload_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

        self.panel_grid = ttk.Frame(self.left, style="Panel.TFrame")
        self.panel_grid.pack(fill=tk.BOTH, expand=False, padx=8, pady=4)

        hint = self.register_i18n(ttk.Label(
            self.left,
            style="Panel.TLabel",
            foreground=self.muted,
            justify=tk.LEFT,
        ), "panel_hint")
        hint.pack(fill=tk.X, padx=8, pady=(4, 8))

        render_section = self.register_i18n(ttk.LabelFrame(self.left, style="Panel.TLabelframe"), "mp4_section")
        render_section.pack(fill=tk.X, padx=8, pady=(4, 8))
        self.add_file_row("output", self.output_var, self.select_output, parent=render_section, button_key="set_output", padx=6)
        self.create_mp4_button = self.register_i18n(ttk.Button(render_section, command=self.create_mp4), "create_mp4")
        self.create_mp4_button.pack(fill=tk.X, padx=6, pady=6)

    def build_center_preview(self):
        topbar = ttk.Frame(self.center)
        topbar.pack(fill=tk.X)
        self.preview_status_var = tk.StringVar(value=self.tr("preview_not_generated"))
        ttk.Label(topbar, textvariable=self.preview_status_var).pack(side=tk.LEFT)
        self.render_preview_button = self.register_i18n(ttk.Button(topbar, command=self.render_preview), "render_preview")
        self.render_preview_button.pack(side=tk.RIGHT)

        self.preview_canvas = tk.Canvas(self.center, bg="#111214", highlightthickness=1, highlightbackground="#555")
        self.preview_canvas.pack(fill=tk.BOTH, expand=True, pady=(6, 6))
        self.preview_canvas.bind("<Configure>", lambda e: self.redraw_current_preview())

        preview_text_frame = ttk.Frame(self.center)
        preview_text_frame.pack(fill=tk.X)
        self.preview_text_label = self.register_i18n(ttk.Label(preview_text_frame), "preview_subtitle")
        self.preview_text_label.pack(side=tk.LEFT)
        self.preview_text_var = tk.StringVar(value=self.preview_placeholder_text())
        self.preview_text_entry = ttk.Entry(preview_text_frame, textvariable=self.preview_text_var)
        self.preview_text_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self.longest_srt_button = self.register_i18n(ttk.Button(preview_text_frame, command=self.set_longest_srt_preview_text), "longest_srt")
        self.longest_srt_button.pack(side=tk.LEFT)
        self.preview_text_entry.bind("<KeyRelease>", lambda e: self.simple_preview())

    def build_generic_drop_area(self):
        generic = self.register_i18n(ttk.LabelFrame(self.right, style="Panel.TLabelframe"), "generic_drop_title")
        generic.pack(fill=tk.X, padx=8, pady=(8, 4))
        generic_inner = self.register_i18n(tk.Label(
            generic,
            bg="#26282f",
            fg=self.fg,
            height=5,
            relief=tk.GROOVE,
        ), "generic_drop")
        generic_inner.pack(fill=tk.X, padx=6, pady=6)
        self.register_drop(generic_inner, lambda event: self.handle_drop(event, preset_id=None))

    def build_all_presets_selector(self):
        combo_frame = ttk.Frame(self.right, style="Panel.TFrame")
        combo_frame.pack(fill=tk.X, padx=8, pady=(0, 6))
        self.all_presets_label = self.register_i18n(ttk.Label(combo_frame), "all_presets")
        self.all_presets_label.pack(side=tk.LEFT)
        self.preset_combo_var = tk.StringVar()
        self.preset_combo = ttk.Combobox(combo_frame, textvariable=self.preset_combo_var, state="readonly", width=38, style="Readable.TCombobox")
        self.preset_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self.preset_combo.bind("<<ComboboxSelected>>", lambda e: self.on_combo_preset_selected())
        self.apply_preset_button = self.register_i18n(ttk.Button(combo_frame, command=self.on_combo_preset_selected), "apply")
        self.apply_preset_button.pack(side=tk.LEFT)

    def build_right_controls(self):
        pad = {"padx": 8, "pady": 4}
        lang_frame = ttk.Frame(self.right, style="Panel.TFrame")
        lang_frame.pack(fill=tk.X, padx=8, pady=(8, 4))
        self.language_label = self.register_i18n(ttk.Label(lang_frame, style="Panel.TLabel", width=17), "language")
        self.language_label.pack(side=tk.LEFT)
        self.language_combo = ttk.Combobox(lang_frame, textvariable=self.language_var, values=["日本語", "English"], state="readonly", width=12, style="Readable.TCombobox")
        self.language_combo.pack(side=tk.LEFT, padx=(4, 0))
        self.language_combo.bind("<<ComboboxSelected>>", self.on_language_changed)

        self.input_files_label = self.register_i18n(ttk.Label(self.right, style="Panel.TLabel"), "input_files")
        self.input_files_label.pack(anchor=tk.W, **pad)

        self.add_file_row("image", self.image_var, self.select_image)
        self.add_file_row("audio", self.audio_var, self.select_audio)
        self.add_file_row("srt", self.srt_var, self.select_srt)

        self.build_generic_drop_area()

        ttk.Separator(self.right).pack(fill=tk.X, padx=8, pady=8)
        self.current_style_label = self.register_i18n(ttk.Label(self.right, style="Panel.TLabel"), "current_style")
        self.current_style_label.pack(anchor=tk.W, **pad)

        self.source_preset_var = tk.StringVar(value=self.tr("source_none"))
        ttk.Label(self.right, textvariable=self.source_preset_var, style="Panel.TLabel", foreground=self.muted).pack(anchor=tk.W, **pad)

        self.fontname_enabled = tk.BooleanVar(value=True)
        self.fontname_var = tk.StringVar()
        self.fontsize_enabled = tk.BooleanVar(value=True)
        self.fontsize_var = tk.StringVar()
        self.alignment_var = tk.StringVar()
        self.margin_enabled = tk.BooleanVar(value=True)
        self.margin_var = tk.StringVar()

        self.add_fontname_row("font", self.fontname_enabled, self.fontname_var)
        self.add_nullable_entry("size", self.fontsize_enabled, self.fontsize_var, width=8)
        size_tweak = ttk.Frame(self.right, style="Panel.TFrame")
        size_tweak.pack(fill=tk.X, padx=8, pady=(0, 4))
        ttk.Label(size_tweak, text="", style="Panel.TLabel", width=16).pack(side=tk.LEFT)
        for label, delta in [("-5", -5), ("-1", -1), ("+1", 1), ("+5", 5)]:
            ttk.Button(size_tweak, text=label, command=lambda d=delta: self.bump_fontsize(d)).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)
        self.add_alignment_row()
        self.add_nullable_entry("MarginV", self.margin_enabled, self.margin_var, width=8)

        tweak = ttk.Frame(self.right, style="Panel.TFrame")
        tweak.pack(fill=tk.X, padx=8, pady=4)
        ttk.Label(tweak, text="", style="Panel.TLabel", width=16).pack(side=tk.LEFT)
        for label, delta in [("-10", -10), ("-1", -1), ("+1", 1), ("+10", 10)]:
            ttk.Button(tweak, text=label, command=lambda d=delta: self.bump_margin(d)).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)

        for var in [self.fontname_enabled, self.fontname_var, self.fontsize_enabled, self.fontsize_var, self.alignment_var, self.margin_enabled, self.margin_var]:
            try:
                var.trace_add("write", lambda *args: self.on_style_var_changed())
            except Exception:
                pass

        ttk.Separator(self.right).pack(fill=tk.X, padx=8, pady=8)
        self.build_all_presets_selector()
        preset_buttons = ttk.Frame(self.right, style="Panel.TFrame")
        preset_buttons.pack(fill=tk.X, padx=8, pady=(0, 4))
        self.reset_button = self.register_i18n(ttk.Button(preset_buttons, command=self.reset_to_preset, style="PresetAction.TButton"), "reset_preset_short")
        self.reset_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        self.save_new_button = self.register_i18n(ttk.Button(preset_buttons, command=self.save_as_new_preset, style="PresetAction.TButton"), "save_new_preset_short")
        self.save_new_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        self.overwrite_button = self.register_i18n(ttk.Button(preset_buttons, command=self.overwrite_current_preset, style="PresetAction.TButton"), "overwrite_preset_short")
        self.overwrite_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        self.delete_preset_button = self.register_i18n(ttk.Button(preset_buttons, command=self.delete_selected_preset, style="PresetAction.TButton"), "delete_preset_short")
        self.delete_preset_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))

    def add_file_row(self, label_key: str, var: tk.StringVar, command, parent=None, button_key: str = "select", padx: int = 8):
        parent = parent or self.right
        frame = ttk.Frame(parent, style="Panel.TFrame")
        frame.pack(fill=tk.X, padx=padx, pady=2)
        label = self.register_i18n(ttk.Label(frame, style="Panel.TLabel", width=14), label_key)
        label.pack(side=tk.LEFT)
        ttk.Label(frame, textvariable=var, style="Panel.TLabel", foreground=self.muted, width=28).pack(side=tk.LEFT, fill=tk.X, expand=True)
        button = self.register_i18n(ttk.Button(frame, command=command), button_key)
        button.pack(side=tk.RIGHT)

    def available_font_families(self) -> List[str]:
        extras = {"UD デジタル 教科書体 NK", "Yu Gothic UI", "メイリオ", "Meiryo", "Arial"}
        try:
            families = set(tkfont.families(self.root))
        except Exception:
            families = set()
        return sorted(families | extras, key=lambda x: x.lower())

    def add_fontname_row(self, label_key: str, enabled_var: tk.BooleanVar, value_var: tk.StringVar):
        frame = ttk.Frame(self.right, style="Panel.TFrame")
        frame.pack(fill=tk.X, padx=8, pady=2)
        cb = ttk.Checkbutton(frame, variable=enabled_var)
        cb.pack(side=tk.LEFT)
        label = self.register_i18n(ttk.Label(frame, style="Panel.TLabel", width=14), label_key)
        label.pack(side=tk.LEFT)
        # state=normal allows manual entry for ffmpeg font family names that Tk may not enumerate.
        self.fontname_combo = ttk.Combobox(frame, textvariable=value_var, values=self.available_font_families(), state="normal", width=24, style="Readable.TCombobox")
        self.fontname_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)

    def add_nullable_entry(self, label_key: str, enabled_var: tk.BooleanVar, value_var: tk.StringVar, width: int = 24):
        frame = ttk.Frame(self.right, style="Panel.TFrame")
        frame.pack(fill=tk.X, padx=8, pady=2)
        cb = ttk.Checkbutton(frame, variable=enabled_var)
        cb.pack(side=tk.LEFT)
        if label_key in UI_TEXT["日本語"]:
            label = self.register_i18n(ttk.Label(frame, style="Panel.TLabel", width=14), label_key)
        else:
            label = ttk.Label(frame, text=label_key, style="Panel.TLabel", width=14)
        label.pack(side=tk.LEFT)
        ttk.Entry(frame, textvariable=value_var, width=width).pack(side=tk.LEFT, fill=tk.X, expand=True)

    def add_plain_entry(self, label: str, value_var: tk.StringVar, width: int = 24):
        frame = ttk.Frame(self.right, style="Panel.TFrame")
        frame.pack(fill=tk.X, padx=8, pady=2)
        ttk.Label(frame, text="", style="Panel.TLabel", width=2).pack(side=tk.LEFT)
        ttk.Label(frame, text=label, style="Panel.TLabel", width=14).pack(side=tk.LEFT)
        ttk.Entry(frame, textvariable=value_var, width=width).pack(side=tk.LEFT, fill=tk.X, expand=True)

    def add_alignment_row(self):
        frame = ttk.Frame(self.right, style="Panel.TFrame")
        frame.pack(fill=tk.X, padx=8, pady=2)
        ttk.Label(frame, text="", style="Panel.TLabel", width=2).pack(side=tk.LEFT)
        ttk.Label(frame, text="Alignment", style="Panel.TLabel", width=14).pack(side=tk.LEFT)
        self.alignment_combo = ttk.Combobox(frame, textvariable=self.alignment_var, values=self.alignment_values(), state="readonly", width=14, style="Readable.TCombobox")
        self.alignment_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)

    def build_bottom(self, main):
        bottom = ttk.Frame(main)
        bottom.pack(fill=tk.BOTH, expand=False, pady=(8, 0))

        jobs_frame = ttk.Frame(bottom)
        jobs_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 8))
        self.jobs_label = self.register_i18n(ttk.Label(jobs_frame), "jobs")
        self.jobs_label.pack(anchor=tk.W)
        self.jobs_tree = ttk.Treeview(jobs_frame, columns=("status", "output"), show="headings", height=7)
        self.jobs_tree.heading("status", text=self.tr("job_status"))
        self.jobs_tree.heading("output", text=self.tr("job_output"))
        self.jobs_tree.column("status", width=110, minwidth=90, stretch=False)
        self.jobs_tree.column("output", width=260, minwidth=180, stretch=True)
        self.jobs_tree.pack(fill=tk.BOTH, expand=True)

        log_frame = ttk.Frame(bottom)
        log_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.log_label = self.register_i18n(ttk.Label(log_frame), "log")
        self.log_label.pack(anchor=tk.W)
        self.log_text = tk.Text(log_frame, height=8, bg="#111214", fg=self.fg, insertbackground=self.fg, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        for msg in self.pending_logs:
            self.log(msg)
        self.pending_logs.clear()

    def register_drop(self, widget, callback):
        if not DND_AVAILABLE:
            return
        try:
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<Drop>>", callback)
        except Exception as exc:
            self.log(f"Drop登録エラー: {exc}")

    # -----------------------------
    # Panel rendering
    # -----------------------------
    def set_page(self, index: int):
        self.current_page_index = index
        self.render_panel()

    def rename_page(self):
        page = self.store.panel_pages[self.current_page_index]
        current_name = self.page_display_name(page, self.current_page_index)
        new_name = simpledialog.askstring("ページ名変更", "新しいページ名:", initialvalue=current_name, parent=self.root)
        if new_name:
            page["name"] = localized_record(new_name, self.language_code(), page.get("name"))
            self.store.save()
            self.render_panel()

    def render_panel(self):
        for child in self.panel_grid.winfo_children():
            child.destroy()
        if not self.store.panel_pages:
            return
        page = self.store.panel_pages[self.current_page_index]
        rows = int(page.get("rows", 5))
        cols = int(page.get("cols", 4))
        slot_map = {int(s.get("slot", 0)): s for s in page.get("slots", [])}
        for i, btn in enumerate(self.page_buttons):
            if i < len(self.store.panel_pages):
                name = self.page_display_name(self.store.panel_pages[i], i)
                btn.config(text=name, bg=self.accent if i == self.current_page_index else "#3a3d44")
        for r in range(rows):
            self.panel_grid.grid_rowconfigure(r, weight=1)
            for c in range(cols):
                self.panel_grid.grid_columnconfigure(c, weight=1)
                slot_no = r * cols + c + 1
                slot = slot_map.get(slot_no)
                label = self.tr("empty_slot") if not slot else self.slot_display_label(slot)
                preset_id = None if not slot else slot.get("preset_id")
                full_name = "" if not preset_id else self.label_for_preset(preset_id)
                bg = "#343842" if preset_id else "#24262b"
                fg = self.fg if preset_id else "#777"
                btn = tk.Button(
                    self.panel_grid,
                    text=label,
                    width=12,
                    height=3,
                    bg=bg,
                    fg=fg,
                    activebackground="#4a4d55",
                    activeforeground=self.fg,
                    relief=tk.RAISED,
                    wraplength=90,
                    command=lambda pid=preset_id: self.apply_preset(pid, render=True) if pid else None,
                )
                btn.grid(row=r, column=c, padx=3, pady=3, sticky="nsew")
                if preset_id:
                    btn.tooltip = ToolTip(btn, full_name)
                    self.register_drop(btn, lambda event, pid=preset_id: self.handle_drop(event, preset_id=pid))

    def label_for_preset(self, preset_id: Optional[str]) -> str:
        p = self.store.preset_by_id(preset_id or "")
        return self.preset_display_name(p) if p else "?"

    def reload_presets(self):
        self.store.load()
        self.refresh_all_preset_combo()
        self.render_panel()
        self.log("presets.json を再読込しました。")

    # -----------------------------
    # Selection / file loading
    # -----------------------------
    def select_image(self):
        path = filedialog.askopenfilename(filetypes=[("Image", "*.jpg *.jpeg *.png *.bmp *.webp"), ("All", "*.*")])
        if path:
            self.set_image(path)
            self.simple_preview()

    def select_audio(self):
        path = filedialog.askopenfilename(filetypes=[("Audio", "*.mp3 *.wav"), ("All", "*.*")])
        if path:
            self.set_audio(path, auto_srt=True, auto_image=True)

    def select_srt(self):
        path = filedialog.askopenfilename(filetypes=[("SRT", "*.srt"), ("All", "*.*")])
        if path:
            self.set_srt(path)
            self.set_longest_srt_preview_text()
            self.simple_preview()

    def select_output(self):
        initial = self.suggest_output_path()
        path = filedialog.asksaveasfilename(defaultextension=".mp4", initialfile=Path(initial).name if initial else "output.mp4",
                                            filetypes=[("MP4", "*.mp4"), ("All", "*.*")])
        if path:
            self.output_path = path
            self.output_user_selected = True
            self.output_var.set(self.short_path(path))

    def set_image(self, path: str):
        self.image_path = path
        self.image_var.set(self.short_path(path))
        self.log(f"画像を設定: {path}")
        if not self.output_path:
            self.update_output_candidate()

    def set_audio(self, path: str, auto_srt: bool = True, auto_image: bool = False):
        self.audio_path = path
        self.audio_var.set(self.short_path(path))
        self.log(f"音源を設定: {path}")
        if auto_image:
            title_image = sibling_title_image_for_audio(path)
            if title_image:
                self.set_image(title_image)
                self.log(f"音源名_title.png を自動設定: {title_image}")
            else:
                self.log("音源名_title.png は見つかりませんでした。")
        if auto_srt:
            srt = sibling_srt_for_audio(path)
            if srt:
                self.set_srt(srt, auto=True)
            else:
                self.log("同名SRTは見つかりませんでした。字幕を付ける場合は手動で選択してください。")
        self.update_output_candidate()

    def set_srt(self, path: str, auto: bool = False):
        self.srt_path = path
        self.srt_var.set(self.short_path(path))
        self.log(("同名SRTを自動設定: " if auto else "SRTを設定: ") + path)
        self.set_longest_srt_preview_text()

    def update_output_candidate(self):
        if self.output_user_selected:
            return
        suggested = self.suggest_output_path()
        if suggested:
            self.output_path = suggested
            self.output_var.set(self.short_path(suggested))

    def suggest_output_path(self) -> Optional[str]:
        with self.job_lock:
            reserved = set(self.reserved_output_paths)
        if self.audio_path:
            p = Path(self.audio_path)
            return str(unique_available_path(p.with_suffix(".mp4"), reserved))
        # Fallback only for the save dialog before audio is selected. Auto-output is normally audio-based.
        if self.image_path:
            p = Path(self.image_path)
            return str(unique_available_path(p.with_name(p.stem + "_字幕MP4.mp4"), reserved))
        return None

    def short_path(self, path: str) -> str:
        try:
            p = Path(path)
            return p.name
        except Exception:
            return path

    def handle_drop(self, event, preset_id: Optional[str]):
        paths = self.parse_drop_data(event.data)
        if not paths:
            return
        if preset_id:
            self.apply_preset(preset_id, render=False)
        self.load_paths(paths)
        if preset_id:
            self.render_preview()
        else:
            self.simple_preview()

    def parse_drop_data(self, data: str) -> List[str]:
        if DND_AVAILABLE:
            try:
                return [str(x) for x in self.root.tk.splitlist(data)]
            except Exception:
                pass
        # fallback rough parser
        return re.findall(r"\{([^}]+)\}|([^\s]+)", data)

    def load_paths(self, paths: List[str]):
        # Flatten fallback tuple regex if needed
        clean = []
        for p in paths:
            if isinstance(p, tuple):
                p = p[0] or p[1]
            if p:
                clean.append(str(p))
        images, audios, srts, others = classify_paths(clean)
        if len(images) > 1:
            self.log(f"画像が複数あります。先頭のみ使用: {images[0]}")
        if len(audios) > 1:
            self.log(f"音源が複数あります。先頭のみ使用: {audios[0]}")
        if len(srts) > 1:
            self.log(f"SRTが複数あります。先頭のみ使用: {srts[0]}")
        if images:
            self.set_image(images[0])
        if audios:
            self.set_audio(audios[0], auto_srt=True, auto_image=not bool(images))
        if srts:
            self.set_srt(srts[0])  # explicit drop overrides auto-detected SRT
        for other in others:
            self.log(f"未対応ファイルを無視: {other}")

    # -----------------------------
    # Preset application / current style
    # -----------------------------
    def refresh_all_preset_combo(self):
        if not hasattr(self, "preset_combo"):
            return
        self.preset_combo_name_to_id = {}
        names = []
        for p in self.store.presets:
            name = self.preset_display_name(p)
            names.append(name)
            self.preset_combo_name_to_id[name] = p.get("id", "")
        self.preset_combo["values"] = names

    def on_combo_preset_selected(self):
        name = self.preset_combo_var.get()
        preset_id = getattr(self, "preset_combo_name_to_id", {}).get(name) or self.store.preset_name_map(self.language_code()).get(name)
        if preset_id:
            self.apply_preset(preset_id, render=True)

    def selected_preset_id(self) -> Optional[str]:
        name = self.preset_combo_var.get() if hasattr(self, "preset_combo_var") else ""
        return getattr(self, "preset_combo_name_to_id", {}).get(name) or self.store.preset_name_map(self.language_code()).get(name) or self.current_preset_id

    def apply_preset(self, preset_id: Optional[str], render: bool = True):
        if not preset_id:
            return
        p = self.store.preset_by_id(preset_id)
        if not p:
            self.log(f"プリセットが見つかりません: {preset_id}")
            return
        self.current_preset_id = preset_id
        self.working_style = json.loads(json.dumps(p.get("style", {}), ensure_ascii=False))
        self.dirty = False
        self.load_style_to_vars()
        if hasattr(self, "preset_combo_var"):
            self.preset_combo_var.set(self.preset_display_name(p))
        self.log(f"プリセット適用: {self.preset_display_name(p)}")
        self.update_status()
        if render:
            self.render_preview()
        else:
            self.simple_preview()

    def load_style_to_vars(self):
        self._suppress_var_events = True
        st = self.working_style
        self.fontname_enabled.set(st.get("fontname") is not None)
        self.fontname_var.set("" if st.get("fontname") is None else str(st.get("fontname")))
        self.fontsize_enabled.set(st.get("fontsize") is not None)
        self.fontsize_var.set("" if st.get("fontsize") is None else str(st.get("fontsize")))
        self.alignment_var.set(self.format_alignment(self.parse_int(st.get("alignment")) or 6))
        self.margin_enabled.set(st.get("margin_v") is not None)
        self.margin_var.set("" if st.get("margin_v") is None else str(st.get("margin_v")))
        self._suppress_var_events = False

    def vars_to_style(self) -> Dict[str, Any]:
        style = dict(self.working_style) if self.working_style else {}
        style["fontname"] = self.fontname_var.get().strip() if self.fontname_enabled.get() and self.fontname_var.get().strip() else None
        style["fontsize"] = self.parse_int(self.fontsize_var.get()) if self.fontsize_enabled.get() else None
        style["alignment"] = self.parse_int(self.alignment_var.get())
        style["margin_v"] = self.parse_int(self.margin_var.get()) if self.margin_enabled.get() else None
        return style

    def parse_int(self, s: str) -> Optional[int]:
        s = str(s).strip()
        if s == "":
            return None
        match = re.search(r"-?\d+(?:\.\d+)?", s)
        if match:
            s = match.group(0)
        try:
            return int(float(s))
        except Exception:
            return None

    def on_style_var_changed(self):
        if self._suppress_var_events:
            return
        self.working_style = self.vars_to_style()
        if self.current_preset_id:
            self.dirty = True
        self.update_status()
        self.simple_preview()

    def bump_margin(self, delta: int):
        self.margin_enabled.set(True)
        cur = self.parse_int(self.margin_var.get()) or 0
        self.margin_var.set(str(cur + delta))

    def bump_fontsize(self, delta: int):
        self.fontsize_enabled.set(True)
        cur = self.parse_int(self.fontsize_var.get())
        if cur is None:
            cur = 20
        self.fontsize_var.set(str(max(1, cur + delta)))

    def reset_to_preset(self):
        if not self.current_preset_id:
            return
        self.apply_preset(self.current_preset_id, render=True)

    def update_status(self):
        if self.current_preset_id:
            p = self.store.preset_by_id(self.current_preset_id)
            name = self.preset_display_name(p) if p else self.current_preset_id
            suffix = self.tr("changed") if self.dirty else ""
            self.source_preset_var.set(f"{self.tr('source_prefix')}{name}{suffix}")
        else:
            self.source_preset_var.set(self.tr("source_none"))

    def save_as_new_preset(self):
        style = self.vars_to_style()
        name = simpledialog.askstring("新規プリセット", "プリセット名:", parent=self.root)
        if not name:
            return
        preset = self.store.add_preset(name, style, language=self.language_code())
        self.refresh_all_preset_combo()
        self.current_preset_id = preset["id"]
        self.working_style = json.loads(json.dumps(style, ensure_ascii=False))
        self.dirty = False
        self.update_status()
        self.log(f"新規プリセット保存: {name}")
        if messagebox.askyesno("パネル追加", "現在のページの空きスロットに追加しますか？"):
            slot = self.store.first_empty_slot(self.current_page_index)
            if slot is None:
                messagebox.showwarning("パネル追加", "現在のページに空きスロットがありません。")
            else:
                label = simpledialog.askstring("パネル表示名", "パネル表示名:", initialvalue=name[:10], parent=self.root)
                self.store.assign_to_slot(self.current_page_index, slot, preset["id"], localized_record(label or name[:10], self.language_code()))
                self.render_panel()

    def overwrite_current_preset(self):
        if not self.current_preset_id:
            messagebox.showinfo("上書き", "選択中プリセットがありません。")
            return
        p = self.store.preset_by_id(self.current_preset_id)
        if not p:
            return
        name = self.preset_display_name(p)
        if not messagebox.askyesno("上書き確認", f"「{name}」を現在の設定で上書きします。よろしいですか？"):
            return
        self.store.update_preset(self.current_preset_id, self.vars_to_style())
        self.dirty = False
        self.update_status()
        self.log(f"プリセットを上書き: {name}")

    def delete_selected_preset(self):
        preset_id = self.selected_preset_id()
        if not preset_id:
            messagebox.showinfo(self.tr("delete_preset_title"), self.tr("delete_preset_none"))
            return
        preset = self.store.preset_by_id(preset_id)
        if not preset:
            messagebox.showinfo(self.tr("delete_preset_title"), self.tr("delete_preset_none"))
            return
        name = self.preset_display_name(preset)
        if not messagebox.askyesno(self.tr("delete_preset_title"), self.tr("delete_preset_confirm").format(name=name)):
            return
        if not self.store.delete_preset(preset_id):
            messagebox.showinfo(self.tr("delete_preset_title"), self.tr("delete_preset_none"))
            return
        if self.current_preset_id == preset_id:
            self.current_preset_id = None
            self.dirty = False
        self.preset_combo_var.set("")
        self.refresh_all_preset_combo()
        self.render_panel()
        self.update_status()
        self.simple_preview()
        self.log(self.tr("delete_preset_done").format(name=name))

    # -----------------------------
    # Preview
    # -----------------------------
    def set_longest_srt_preview_text(self):
        self.preview_text_var.set(srt_preview_text(self.srt_path, self.preview_placeholder_text()))
        self.simple_preview()

    def simple_preview(self):
        try:
            img, placeholder = self.preview_base_image()
            draw = ImageDraw.Draw(img)
            text = self.preview_text_var.get() or self.preview_placeholder_text()
            style = self.vars_to_style() if hasattr(self, "fontname_var") else self.working_style
            font_size = self.estimated_simple_font_size(img.height, style)
            font = load_preview_font(style.get("fontname") or self.store.settings().get("default_preview_font", DEFAULT_PREVIEW_FONT), font_size)
            stroke_width = self.estimated_simple_outline_width(img.height)
            spacing = self.estimated_simple_line_spacing(font_size)
            bbox = draw.multiline_textbbox((0, 0), text, font=font, spacing=spacing, align="center", stroke_width=stroke_width)
            block_w = bbox[2] - bbox[0]
            block_h = bbox[3] - bbox[1]
            x, y = self.estimate_text_origin(img.width, img.height, block_w, block_h, bbox, style)
            draw.multiline_text(
                (x, y),
                text,
                font=font,
                fill="white",
                spacing=spacing,
                align="center",
                stroke_width=stroke_width,
                stroke_fill="black",
            )
            self.display_image(img)
            self.preview_status_var.set(self.tr("simple_preview_placeholder") if placeholder else self.tr("simple_preview"))
        except Exception as exc:
            self.preview_status_var.set("簡易プレビュー失敗")
            self.log(f"簡易プレビュー失敗: {exc}")

    def preview_base_image(self) -> Tuple[Image.Image, bool]:
        if self.image_path and Path(self.image_path).exists():
            return Image.open(self.image_path).convert("RGB"), False
        return Image.new("RGB", PREVIEW_PLACEHOLDER_SIZE, "white"), True

    def estimated_simple_font_size(self, image_height: int, style: Dict[str, Any]) -> int:
        scale = float(self.store.settings().get("preview_font_scale", PREVIEW_FONT_SCALE_DEFAULT))
        fs = style.get("fontsize")
        if fs is not None:
            # ASS/libass scales Fontsize from PlayResY coordinates to the actual video height.
            base = float(fs) * float(image_height) / ASS_PLAY_RES_Y
        else:
            # Approximate ffmpeg/libass default SRT style: Fontsize=16 at PlayResY=288.
            base = ASS_DEFAULT_FONT_SIZE * float(image_height) / ASS_PLAY_RES_Y
        return max(6, int(round(base * scale)))

    def estimated_simple_outline_width(self, image_height: int) -> int:
        return max(1, int(round(float(image_height) / ASS_PLAY_RES_Y)))

    def estimated_simple_line_spacing(self, font_size: int) -> int:
        return max(0, int(round(float(font_size) * 0.18)))

    def estimate_text_origin(
        self,
        image_width: int,
        image_height: int,
        block_width: int,
        block_height: int,
        bbox: Tuple[int, int, int, int],
        style: Dict[str, Any],
    ) -> Tuple[int, int]:
        alignment = self.parse_int(style.get("alignment")) or 2
        margin = style.get("margin_v")
        scaled_margin = 0.0 if margin is None else float(margin) * float(image_height) / ASS_PLAY_RES_Y

        # The project presets use SSA-style values: 6 is top-center, 10 is middle-center.
        horizontal = alignment % 4
        if horizontal == 1:
            left = scaled_margin
        elif horizontal == 3:
            left = float(image_width) - scaled_margin - block_width
        else:
            left = (float(image_width) - block_width) / 2.0

        if 5 <= alignment <= 7:
            top = scaled_margin
        elif 9 <= alignment <= 11:
            top = (float(image_height) - block_height) / 2.0 + scaled_margin
        else:
            top = float(image_height) - scaled_margin - block_height

        return int(round(left - bbox[0])), int(round(top - bbox[1]))

    def display_image(self, img: Image.Image):
        canvas_w = max(10, self.preview_canvas.winfo_width())
        canvas_h = max(10, self.preview_canvas.winfo_height())
        iw, ih = img.size
        scale = min(canvas_w / iw, canvas_h / ih)
        nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
        resized = img.resize((nw, nh), Image.LANCZOS)
        self.preview_photo = ImageTk.PhotoImage(resized)
        self.preview_canvas.delete("all")
        x = (canvas_w - nw) // 2
        y = (canvas_h - nh) // 2
        self.preview_canvas.create_image(x, y, image=self.preview_photo, anchor=tk.NW)
        self.preview_canvas.create_rectangle(x, y, x + nw, y + nh, outline="#777")

    def redraw_current_preview(self):
        if self.render_preview_path and Path(self.render_preview_path).exists() and not self.dirty:
            try:
                img = Image.open(self.render_preview_path).convert("RGB")
                self.display_image(img)
                return
            except Exception:
                pass
        self.simple_preview()

    def render_preview(self):
        if not self.ensure_ffmpeg():
            return
        if self.render_thread and self.render_thread.is_alive():
            self.log("レンダープレビュー生成中です。")
            return
        style = self.vars_to_style()
        text = self.preview_text_var.get() or srt_preview_text(self.srt_path, self.preview_placeholder_text())
        image_path = self.image_path if self.image_path and Path(self.image_path).exists() else None
        self.preview_status_var.set(self.tr("rendering_preview"))
        self.render_thread = threading.Thread(target=self._render_preview_worker, args=(style, text, image_path), daemon=True)
        self.render_thread.start()

    def _render_preview_worker(self, style: Dict[str, Any], text: str, image_path: Optional[str]):
        try:
            with tempfile.TemporaryDirectory(prefix="subtitle_preview_") as td:
                input_image = image_path
                if not input_image:
                    placeholder = str(Path(td) / "placeholder.png")
                    Image.new("RGB", PREVIEW_PLACEHOLDER_SIZE, "white").save(placeholder)
                    input_image = placeholder
                srt = str(Path(td) / "preview.srt")
                out = str(Path(td) / "preview.png")
                write_preview_srt(srt, text)
                vf = f"scale=trunc(iw/2)*2:trunc(ih/2)*2,{make_subtitle_filter(srt, style)}"
                cmd = [self.ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-loop", "1", "-i", input_image, "-vf", vf, "-frames:v", "1", out]
                run_subprocess(cmd, log_func=self.log_threadsafe, check=True)
                final = self.base / "_last_render_preview.png"
                shutil.copy2(out, final)
            self.render_preview_path = str(final)
            self.dirty = False
            self.call_ui_thread(self._render_preview_done)
        except Exception as exc:
            self.log_threadsafe(f"レンダープレビュー失敗: {exc}")
            self.call_ui_thread(lambda: self.preview_status_var.set(self.tr("render_preview_failed")))

    def _render_preview_done(self):
        try:
            img = Image.open(self.render_preview_path).convert("RGB")
            self.display_image(img)
            self.preview_status_var.set(self.tr("render_preview_done"))
            self.update_status()
        except Exception as exc:
            self.log(f"レンダープレビュー表示失敗: {exc}")

    # -----------------------------
    # MP4 generation
    # -----------------------------
    def ensure_ffmpeg(self) -> bool:
        self.ffmpeg = self.ffmpeg or find_tool("ffmpeg")
        self.ffprobe = self.ffprobe or find_tool("ffprobe")
        if not self.ffmpeg or not self.ffprobe:
            messagebox.showerror("ffmpeg", "ffmpeg または ffprobe が見つかりません。binフォルダまたはPATHを確認してください。")
            return False
        return True

    def create_mp4(self):
        if not self.ensure_ffmpeg():
            return
        missing = []
        if not self.image_path:
            missing.append("画像")
        if not self.audio_path:
            missing.append("音源")
        if missing:
            messagebox.showerror("入力不足", "未設定: " + ", ".join(missing))
            return
        output_path = self.reserve_output_path()
        if not output_path:
            return
        style = json.loads(json.dumps(self.vars_to_style(), ensure_ascii=False))
        job = VideoJob(
            id=uuid.uuid4().hex,
            image_path=self.image_path,
            audio_path=self.audio_path,
            srt_path=self.srt_path,
            output_path=output_path,
            style=style,
            created_at=time.strftime("%H:%M:%S"),
        )
        thread = threading.Thread(target=self._create_mp4_worker, args=(job,), daemon=True)
        job.thread = thread
        with self.job_lock:
            self.video_jobs[job.id] = job
        self.update_jobs_view()
        self.log(f"[{job.short_id}] MP4ジョブ投入: {job.output_path}")
        thread.start()
        if not self.output_user_selected:
            self.output_path = None
            self.update_output_candidate()

    def reserve_output_path(self) -> Optional[str]:
        base = self.output_path or self.suggest_output_path()
        if not base:
            messagebox.showerror("出力不足", "出力先を決定できません。音源または出力先を選択してください。")
            return None
        base_path = Path(base)
        with self.job_lock:
            reserved = set(self.reserved_output_paths)
            resolved = str(base_path.resolve()).lower()
            if self.output_user_selected:
                if resolved in {str(Path(p).resolve()).lower() for p in reserved}:
                    messagebox.showerror("出力先重複", f"この出力先は実行中ジョブで使用中です。\n{base}")
                    return None
                if base_path.exists():
                    if not messagebox.askyesno("上書き確認", f"出力ファイルが存在します。上書きしますか？\n{base}"):
                        return None
                output_path = base_path
            else:
                output_path = unique_available_path(base_path, reserved)
            self.reserved_output_paths.add(str(output_path))
        self.output_path = str(output_path)
        self.output_var.set(self.short_path(self.output_path))
        return str(output_path)

    def update_jobs_view(self):
        if not hasattr(self, "jobs_tree"):
            return
        with self.job_lock:
            jobs = list(self.video_jobs.values())
        existing = set(self.jobs_tree.get_children())
        for job in jobs:
            values = (f"{job.status}  {job.created_at}", Path(job.output_path).name)
            if job.id in existing:
                self.jobs_tree.item(job.id, values=values)
            else:
                self.jobs_tree.insert("", tk.END, iid=job.id, values=values)
        for item in existing - {job.id for job in jobs}:
            self.jobs_tree.delete(item)

    def set_job_status(self, job: VideoJob, status: str, error: Optional[str] = None):
        with self.job_lock:
            current = self.video_jobs.get(job.id)
            if current:
                current.status = status
                current.error = error
        self.call_ui_thread(self.update_jobs_view)

    def release_job_output(self, job: VideoJob):
        with self.job_lock:
            self.reserved_output_paths.discard(str(Path(job.output_path)))
        self.call_ui_thread(self.update_output_candidate)

    def job_log_func(self, job: VideoJob):
        return lambda msg: self.log_threadsafe(f"[{job.short_id}] {msg}")

    def _create_mp4_worker(self, job: VideoJob):
        log_func = self.job_log_func(job)
        try:
            self.set_job_status(job, "running")
            self.log_threadsafe(f"[{job.short_id}] MP4作成開始")
            with tempfile.TemporaryDirectory(prefix="subtitle_video_") as td:
                td_path = Path(td)
                work_srt = str(td_path / "subtitle.srt")
                work_wav = str(td_path / "audio.wav")
                has_subtitle = bool(job.srt_path and Path(job.srt_path).exists())
                if has_subtitle:
                    normalize_srt_to_utf8(job.srt_path, work_srt)
                else:
                    self.log_threadsafe(f"[{job.short_id}] SRT未指定: 字幕なしで作成")

                # Convert audio to WAV for stable duration and input handling.
                cmd_audio = [self.ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", job.audio_path, "-vn", work_wav]
                run_subprocess(cmd_audio, log_func=log_func, check=True)

                duration = self.probe_duration(work_wav, log_func=log_func)
                self.log_threadsafe(f"[{job.short_id}] 音声長: {duration:.3f} 秒")

                vf = "scale=trunc(iw/2)*2:trunc(ih/2)*2"
                if has_subtitle:
                    vf = f"{vf},{make_subtitle_filter(work_srt, job.style)}"
                cmd = [
                    self.ffmpeg,
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-loop",
                    "1",
                    "-framerate",
                    "30",
                    "-i",
                    job.image_path,
                    "-i",
                    work_wav,
                    "-map",
                    "0:v",
                    "-map",
                    "1:a:0",
                    "-vf",
                    vf,
                    "-c:v",
                    "libx264",
                    "-tune",
                    "stillimage",
                    "-c:a",
                    "aac",
                    "-ar",
                    "48000",
                    "-b:a",
                    "384k",
                    "-pix_fmt",
                    "yuv420p",
                    "-r",
                    "30",
                    "-movflags",
                    "+faststart",
                    "-t",
                    f"{duration:.3f}",
                    job.output_path,
                ]
                run_subprocess(cmd, log_func=log_func, check=True)
            self.set_job_status(job, "done")
            self.log_threadsafe(f"[{job.short_id}] MP4作成完了: {job.output_path}")
        except Exception as exc:
            self.set_job_status(job, "failed", str(exc))
            self.log_threadsafe(f"[{job.short_id}] MP4作成失敗: {exc}")
        finally:
            self.release_job_output(job)

    def probe_duration(self, path: str, log_func=None) -> float:
        cmd = [self.ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path]
        proc = run_subprocess(cmd, log_func=log_func or self.log_threadsafe, check=True)
        try:
            return float(proc.stdout.strip())
        except Exception:
            return 0.0

    # -----------------------------
    # Logging
    # -----------------------------
    def log(self, msg: str):
        if not hasattr(self, "log_text"):
            self.pending_logs.append(msg)
            return
        ts = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{ts}] {msg}\n")
        self.log_text.see(tk.END)

    def log_threadsafe(self, msg: str):
        self.log_queue.put(msg)

    def call_ui_thread(self, func: Callable[[], None]):
        self.ui_queue.put(func)

    def process_log_queue(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.log(msg)
        except queue.Empty:
            pass
        try:
            while True:
                func = self.ui_queue.get_nowait()
                func()
        except queue.Empty:
            pass
        self.root.after(100, self.process_log_queue)


def main():
    if DND_AVAILABLE:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    root.geometry("1480x900")
    app = App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
