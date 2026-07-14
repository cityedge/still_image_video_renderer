# -*- coding: utf-8 -*-
"""
Still Image Video Renderer
Version 1.1.0

Purpose:
  Create an MP4 video from a still image, an audio file, and an optional SRT subtitle file.
  This is a GUI ffmpeg wrapper with preset panels, drag-and-drop, rendered preview,
  and working-style edits.

Dependencies:
  pip install pillow tkinterdnd2

Distribution note:
  PyInstaller onedir build should include:
    --collect-all tkinterdnd2 --hidden-import tkinterdnd2.TkinterDnD
"""
from __future__ import annotations

import json
import os
import queue
import re
import shutil
import struct
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
from tkinter import colorchooser, filedialog, messagebox, simpledialog
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
APP_VERSION = "1.1.0"
PREVIEW_FONT_SCALE_DEFAULT = 0.76
SETTINGS_VERSION = 9
DEFAULT_PREVIEW_FONT = "Yu Gothic UI"
LANGUAGE_JA = "日本語"
LANGUAGE_EN = "English"
LANGUAGE_CODES = {LANGUAGE_JA: "ja", LANGUAGE_EN: "en", "ja": "ja", "en": "en"}
ASS_PLAY_RES_Y = 288.0
ASS_DEFAULT_FONT_SIZE = 16.0
PREVIEW_PLACEHOLDER_SIZE = (1280, 720)
DEFAULT_PREVIEW_SUBTITLE_JA = "プレビュー用字幕テキスト"
DEFAULT_PREVIEW_SUBTITLE_EN = "Subtitle text for preview"
COVER_ICON_GAP_PX = 2
COVER_TITLE_LINE_GAP_PX = 16
COVER_TITLE_LINE2_INDENT_LIMIT_PX = 400

DEFAULT_COVER_SETTINGS: Dict[str, Any] = {
    "title_line1": "",
    "title_line2": "",
    "title_font": "BIZ UDPゴシック",
    "title_bold": True,
    "title_italic": False,
    "title_line1_size": 60,
    "title_line2_size": 60,
    "title_outline": 2,
    "title_shadow_enabled": False,
    "title_shadow_offset": 3,
    "title_x_pct": 3,
    "title_y_pct": 5,
    "title_line_gap": COVER_TITLE_LINE_GAP_PX,
    "title_line2_indent": 0,
    "title_color": "#FFFFFF",
    "icon1_path": "",
    "icon2_path": "",
}

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
AUDIO_EXTS = {".mp3", ".wav"}
SRT_EXTS = {".srt"}

UI_TEXT = {
    "日本語": {
        "language": "言語 / Language",
        "quick_panel": "クイックパネル",
        "panel_edit": "パネル編集",
        "panel_edit_title": "クイックパネル編集",
        "panel_edit_hint": "移動元のパネルを選び、移動先をクリックします。空きスロットなら移動、使用中スロットなら入れ替えます。",
        "selected_panel": "選択中:",
        "no_panel_selected": "未選択",
        "panel_label": "表示名",
        "apply_panel_label": "表示名を適用",
        "clear_panel_slot": "選択スロットを空にする",
        "close": "閉じる",
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
        "cover_section": "タイトル・アイコン",
        "title_font": "タイトルフォント",
        "title_line1": "タイトル 1行目",
        "title_line2": "タイトル 2行目",
        "title_size": "サイズ (px)",
        "title_bold": "太字",
        "title_italic": "斜体",
        "title_color": "色選択",
        "title_outline": "縁取り (px)",
        "title_shadow": "影",
        "title_shadow_offset": "影ずれ (px)",
        "title_x": "X（画像幅%）",
        "title_y": "Y（画像高%）",
        "title_line_gap": "間隔",
        "title_line2_indent": "インデント",
        "icon1": "アイコン 1",
        "icon2": "アイコン 2",
        "clear": "消去",
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
        "panel_edit": "Edit Panel",
        "panel_edit_title": "Quick Panel Editor",
        "panel_edit_hint": "Select a source panel, then click a destination. Empty slots move it; occupied slots swap positions.",
        "selected_panel": "Selected:",
        "no_panel_selected": "None",
        "panel_label": "Label",
        "apply_panel_label": "Apply Label",
        "clear_panel_slot": "Clear Selected Slot",
        "close": "Close",
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
        "cover_section": "Title and Icons",
        "title_font": "Title font",
        "title_line1": "Title line 1",
        "title_line2": "Title line 2",
        "title_size": "Size (px)",
        "title_bold": "Bold",
        "title_italic": "Italic",
        "title_color": "Choose color",
        "title_outline": "Outline (px)",
        "title_shadow": "Shadow",
        "title_shadow_offset": "Shadow offset (px)",
        "title_x": "X (% width)",
        "title_y": "Y (% height)",
        "title_line_gap": "Gap",
        "title_line2_indent": "Indent",
        "icon1": "Icon 1",
        "icon2": "Icon 2",
        "clear": "Clear",
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
    "日本語": {6: "6（中央上）", 10: "10（中央）", 2: "2（中央下）"},
    "English": {6: "6 (Top center)", 10: "10 (Center)", 2: "2 (Bottom center)"},
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
        "cover": dict(DEFAULT_COVER_SETTINGS),
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


def load_external_default_presets(fallback: Dict[str, Any]) -> Dict[str, Any]:
    candidates: List[Path] = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / "presets_default.json")
    candidates.extend([
        Path(__file__).resolve().parent / "presets_default.json",
        Path.cwd() / "presets_default.json",
    ])
    seen: set[Path] = set()
    for path in candidates:
        try:
            resolved = path.resolve()
        except Exception:
            resolved = path
        if resolved in seen:
            continue
        seen.add(resolved)
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict) and isinstance(data.get("presets"), list) and isinstance(data.get("panel_pages"), list):
            data.setdefault("settings", {})["settings_version"] = SETTINGS_VERSION
            return data
    return fallback


apply_default_preset_display_data(DEFAULT_PRESETS)
DEFAULT_PRESETS = load_external_default_presets(DEFAULT_PRESETS)


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
    cover_settings: Dict[str, Any]
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
        # Pre-1.0 preset data is reset to the v1 default layout.
        if version < 4:
            self.data = json.loads(json.dumps(DEFAULT_PRESETS, ensure_ascii=False))
            self.data.setdefault("settings", {})["settings_version"] = SETTINGS_VERSION
            self.save()
            return
        if version < SETTINGS_VERSION:
            settings["preview_font_scale"] = PREVIEW_FONT_SCALE_DEFAULT
            settings.setdefault("default_preview_font", DEFAULT_PREVIEW_FONT)
            migrate_cover_settings(settings, version)
            settings["settings_version"] = SETTINGS_VERSION
            self.save()
            return
        if migrate_cover_settings(settings, version):
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
            settings = self.data.setdefault("settings", {})
            settings["settings_version"] = SETTINGS_VERSION
            ensure_cover_settings(settings)
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

    def slot_by_number(self, page_index: int, slot: int) -> Optional[Dict[str, Any]]:
        if page_index < 0 or page_index >= len(self.panel_pages):
            return None
        for item in self.panel_pages[page_index].setdefault("slots", []):
            if int(item.get("slot", 0)) == int(slot):
                return item
        return None

    def set_slot_label(self, page_index: int, slot: int, label: Any):
        item = self.slot_by_number(page_index, slot)
        if not item:
            return False
        item["label"] = label
        self.save()
        return True

    def clear_slot(self, page_index: int, slot: int) -> bool:
        if page_index < 0 or page_index >= len(self.panel_pages):
            return False
        slots = self.panel_pages[page_index].setdefault("slots", [])
        before = len(slots)
        slots[:] = [s for s in slots if int(s.get("slot", 0)) != int(slot)]
        if len(slots) == before:
            return False
        self.save()
        return True

    def move_or_swap_slot(self, source_page: int, source_slot: int, target_page: int, target_slot: int) -> bool:
        if (source_page, source_slot) == (target_page, target_slot):
            return False
        source = self.slot_by_number(source_page, source_slot)
        if not source:
            return False
        target = self.slot_by_number(target_page, target_slot)
        source_copy = dict(source)
        target_copy = dict(target) if target else None
        for page_index, slot_no in {(source_page, source_slot), (target_page, target_slot)}:
            slots = self.panel_pages[page_index].setdefault("slots", [])
            slots[:] = [s for s in slots if int(s.get("slot", 0)) != int(slot_no)]
        source_copy["slot"] = int(target_slot)
        self.panel_pages[target_page].setdefault("slots", []).append(source_copy)
        if target_copy:
            target_copy["slot"] = int(source_slot)
            self.panel_pages[source_page].setdefault("slots", []).append(target_copy)
        for page in self.panel_pages:
            page.setdefault("slots", []).sort(key=lambda x: int(x.get("slot", 0)))
        self.save()
        return True


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


def sibling_audio_for_srt(srt_path: str) -> Optional[str]:
    p = Path(srt_path)
    for ext in (".mp3", ".wav"):
        candidate = p.with_suffix(ext)
        if candidate.exists():
            return str(candidate)
    try:
        for child in p.parent.iterdir():
            if child.is_file() and child.suffix.lower() in AUDIO_EXTS and child.stem.lower() == p.stem.lower():
                return str(child)
    except Exception:
        pass
    return None


def sibling_title_image_for_path(path: str) -> Optional[str]:
    """Return <stem>_title.png next to a media or SRT file, with a case-insensitive fallback."""
    p = Path(path)
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


def sibling_title_image_for_audio(audio_path: str) -> Optional[str]:
    return sibling_title_image_for_path(audio_path)


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


_WINDOWS_FONT_FACE_INDEX: Optional[Dict[str, List[Tuple[str, int, str]]]] = None


def normalize_font_family_name(value: str) -> str:
    return re.sub(r"\s+", " ", value.lstrip("@").strip()).casefold()


def windows_font_paths() -> List[Path]:
    paths: set[Path] = set()
    fonts_dir = windows_fonts_dir()
    try:
        paths.update(path for path in fonts_dir.iterdir() if path.suffix.lower() in {".ttf", ".otf", ".ttc"})
    except OSError:
        pass
    if os.name != "nt":
        return sorted(paths)
    try:
        import winreg
        registry_paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"),
        ]
        for hive, key_path in registry_paths:
            try:
                with winreg.OpenKey(hive, key_path) as key:
                    for index in range(winreg.QueryInfoKey(key)[1]):
                        _label, value, _kind = winreg.EnumValue(key, index)
                        if not isinstance(value, str):
                            continue
                        path = Path(value)
                        if not path.is_absolute():
                            path = fonts_dir / path
                        if path.suffix.lower() in {".ttf", ".otf", ".ttc"} and path.exists():
                            paths.add(path)
            except OSError:
                continue
    except ImportError:
        pass
    return sorted(paths)


def sfnt_face_offsets(font_file) -> List[int]:
    font_file.seek(0)
    signature = font_file.read(4)
    if signature != b"ttcf":
        return [0]
    header = font_file.read(8)
    if len(header) != 8:
        return []
    _version, count = struct.unpack(">II", header)
    raw_offsets = font_file.read(count * 4)
    if len(raw_offsets) != count * 4:
        return []
    return list(struct.unpack(f">{count}I", raw_offsets))


def decode_font_name(raw: bytes, platform_id: int) -> str:
    try:
        if platform_id in (0, 3):
            return raw.decode("utf-16-be")
        if platform_id == 1:
            return raw.decode("mac_roman")
        return raw.decode("latin-1")
    except UnicodeDecodeError:
        return ""


def sfnt_face_family_and_style(font_file, face_offset: int) -> Tuple[List[str], str]:
    font_file.seek(face_offset)
    header = font_file.read(12)
    if len(header) != 12:
        return [], ""
    table_count = struct.unpack(">H", header[4:6])[0]
    directory = font_file.read(table_count * 16)
    if len(directory) != table_count * 16:
        return [], ""
    name_table_offset = None
    for index in range(table_count):
        entry = directory[index * 16:(index + 1) * 16]
        if entry[:4] == b"name":
            _checksum, offset, _length = struct.unpack(">III", entry[4:16])
            name_table_offset = offset
            break
    if name_table_offset is None:
        return [], ""
    font_file.seek(name_table_offset)
    name_header = font_file.read(6)
    if len(name_header) != 6:
        return [], ""
    _format, count, string_offset = struct.unpack(">HHH", name_header)
    records = font_file.read(count * 12)
    families: List[str] = []
    styles: List[str] = []
    for index in range(count):
        record = records[index * 12:(index + 1) * 12]
        if len(record) != 12:
            continue
        platform_id, _encoding_id, _language_id, name_id, length, offset = struct.unpack(">HHHHHH", record)
        if name_id not in (1, 2, 16, 17):
            continue
        font_file.seek(name_table_offset + string_offset + offset)
        value = decode_font_name(font_file.read(length), platform_id).strip()
        if not value:
            continue
        if name_id in (1, 16):
            families.append(value)
        else:
            styles.append(value)
    return list(dict.fromkeys(families)), " ".join(dict.fromkeys(styles))


def windows_font_face_index() -> Dict[str, List[Tuple[str, int, str]]]:
    global _WINDOWS_FONT_FACE_INDEX
    if _WINDOWS_FONT_FACE_INDEX is not None:
        return _WINDOWS_FONT_FACE_INDEX
    index: Dict[str, List[Tuple[str, int, str]]] = {}
    for path in windows_font_paths():
        try:
            with path.open("rb") as font_file:
                for face_index, face_offset in enumerate(sfnt_face_offsets(font_file)):
                    families, style = sfnt_face_family_and_style(font_file, face_offset)
                    for family in families:
                        key = normalize_font_family_name(family)
                        if key:
                            index.setdefault(key, []).append((str(path), face_index, style))
        except OSError:
            continue
    _WINDOWS_FONT_FACE_INDEX = index
    return index


def find_font_spec(fontname: Optional[str], bold: bool = False) -> Tuple[Optional[str], int]:
    if fontname:
        direct_path = Path(fontname)
        if direct_path.is_file():
            return str(direct_path), 0
        matches = windows_font_face_index().get(normalize_font_family_name(fontname), [])
        if matches:
            def score(match: Tuple[str, int, str]) -> int:
                style = match[2].casefold()
                is_bold = any(word in style for word in ("bold", "black", "太字", "ボールド"))
                return 0 if is_bold == bold else 1
            path, face_index, _style = min(matches, key=score)
            return path, face_index
    # Linux fallback for sandbox/local non-Windows.
    for path in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    ]:
        if Path(path).exists():
            return path, 0
    return None, 0


def find_font_file(fontname: Optional[str], bold: bool = False) -> Optional[str]:
    path, _face_index = find_font_spec(fontname, bold=bold)
    return path


def load_preview_font(fontname: Optional[str], size: int, bold: bool = False):
    path, face_index = find_font_spec(fontname, bold=bold)
    if path:
        try:
            return ImageFont.truetype(path, max(1, int(size)), index=face_index)
        except Exception:
            pass
    return ImageFont.load_default()


def ensure_cover_settings(settings: Dict[str, Any]) -> bool:
    """Add new cover settings without disturbing existing user values."""
    cover = settings.get("cover")
    changed = not isinstance(cover, dict)
    if not isinstance(cover, dict):
        cover = {}
        settings["cover"] = cover
    for key, value in DEFAULT_COVER_SETTINGS.items():
        if key not in cover:
            cover[key] = value
            changed = True
    return changed


def migrate_cover_settings(settings: Dict[str, Any], version: int) -> bool:
    existing_cover = settings.get("cover") if isinstance(settings.get("cover"), dict) else {}
    had_x = "title_x_pct" in existing_cover
    had_y = "title_y_pct" in existing_cover
    legacy_layout = str(existing_cover.get("title_layout") or "top_left")
    legacy_offset_x = existing_cover.get("title_offset_x_pct", 0)
    legacy_offset_y = existing_cover.get("title_offset_y_pct", 0)
    changed = ensure_cover_settings(settings)
    cover = settings["cover"]
    # Version 5 was introduced during development with a temporary visual
    # baseline. Update that exact baseline, while preserving any user edits.
    if version < 6:
        old_defaults = {
            "title_font": "Yu Gothic UI",
            "title_line1_size": 72,
            "title_line2_size": 72,
            "title_outline": 3,
            "title_shadow_enabled": True,
            "title_shadow_offset": 3,
        }
        if all(cover.get(key) == value for key, value in old_defaults.items()):
            for key, value in DEFAULT_COVER_SETTINGS.items():
                if cover.get(key) != value:
                    cover[key] = value
                    changed = True
    if version < 7:
        # The previous controls used a corner preset plus an offset. The new
        # controls are absolute percentages from the upper-left corner.
        if legacy_layout == "top_left":
            try:
                migrated_x = max(0, min(100, 3 + int(legacy_offset_x)))
                migrated_y = max(0, min(100, 3 + int(legacy_offset_y)))
            except (TypeError, ValueError):
                migrated_x, migrated_y = 3, 3
        else:
            migrated_x, migrated_y = 3, 3
        if not had_x and cover.get("title_x_pct") != migrated_x:
            cover["title_x_pct"] = migrated_x
            changed = True
        if not had_y and cover.get("title_y_pct") != migrated_y:
            cover["title_y_pct"] = migrated_y
            changed = True
    return changed


def get_cover_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    migrate_cover_settings(settings, SETTINGS_VERSION)
    return settings["cover"]


def parse_cover_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def normalize_cover_color(value: Any, default: str = "#FFFFFF") -> str:
    color = str(value or "").strip()
    if re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
        return color.upper()
    return default


def render_title_line_image(
    text: str,
    fontname: Optional[str],
    size: int,
    outline: int,
    bold: bool,
    italic: bool,
    fill: str,
    stroke_fill: str,
) -> Image.Image:
    font = load_preview_font(fontname, max(6, size), bold=bold)
    measure = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bbox = measure.textbbox((0, 0), text, font=font, stroke_width=outline)
    width = max(1, bbox[2] - bbox[0])
    height = max(1, bbox[3] - bbox[1])
    line = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ImageDraw.Draw(line).text(
        (-bbox[0], -bbox[1]),
        text,
        font=font,
        fill=fill,
        stroke_width=outline,
        stroke_fill=stroke_fill,
    )
    if not italic:
        return line

    # Many Japanese system fonts have no italic face. Apply a light shear so
    # the italic checkbox has a visible and consistent result for every font.
    shear = 0.20
    extra_width = max(1, int(round(height * shear)))
    return line.transform(
        (width + extra_width, height),
        Image.Transform.AFFINE,
        (1, shear, -extra_width, 0, 1, 0),
        resample=Image.Resampling.BICUBIC,
    )


def title_line_for_width(
    text: str,
    fontname: Optional[str],
    requested_size: int,
    max_width: int,
    outline: int,
    bold: bool,
    italic: bool,
    fill: str = "white",
    stroke_fill: str = "black",
) -> Image.Image:
    """Keep the requested pixel size unless a line would leave the canvas."""
    size = max(6, requested_size)
    while True:
        line = render_title_line_image(text, fontname, size, outline, bold, italic, fill, stroke_fill)
        if line.width <= max_width or size <= 6:
            return line
        size -= 1


def load_cover_icon(path: str) -> Optional[Image.Image]:
    if not path or not Path(path).exists():
        return None
    try:
        with Image.open(path) as source:
            return source.convert("RGBA")
    except Exception:
        return None


def compose_cover_image(base_image: Image.Image, cover: Dict[str, Any]) -> Image.Image:
    """Add title and native-size icons to a copy of a still image."""
    image = base_image.convert("RGBA")
    width, height = image.size
    title_font = str(cover.get("title_font") or DEFAULT_PREVIEW_FONT)
    title_bold = bool(cover.get("title_bold"))
    title_italic = bool(cover.get("title_italic"))
    title_color = normalize_cover_color(cover.get("title_color"))
    outline = max(0, parse_cover_int(cover.get("title_outline")))
    shadow_offset = max(0, parse_cover_int(cover.get("title_shadow_offset")))
    shadow_enabled = bool(cover.get("title_shadow_enabled"))
    max_width = max(1, width)
    title_x = max(0, min(100, parse_cover_int(cover.get("title_x_pct"), 3)))
    title_y = max(0, min(100, parse_cover_int(cover.get("title_y_pct"), 3)))
    left = int(round(width * title_x / 100.0))
    top = int(round(height * title_y / 100.0))

    lines: List[Tuple[str, int, Image.Image, bool]] = []
    for text_key, size_key in (("title_line1", "title_line1_size"), ("title_line2", "title_line2_size")):
        text = str(cover.get(text_key) or "").strip()
        if not text:
            continue
        try:
            requested_size = max(6, int(cover.get(size_key) or 6))
        except (TypeError, ValueError):
            requested_size = 6
        line = title_line_for_width(
            text,
            title_font,
            requested_size,
            max_width,
            outline,
            title_bold,
            title_italic,
            fill=title_color,
        )
        lines.append((text, requested_size, line, text_key == "title_line2"))

    if lines:
        line_gap = max(0, parse_cover_int(cover.get("title_line_gap"), COVER_TITLE_LINE_GAP_PX))
        line2_indent = max(
            -COVER_TITLE_LINE2_INDENT_LIMIT_PX,
            min(COVER_TITLE_LINE2_INDENT_LIMIT_PX, parse_cover_int(cover.get("title_line2_indent"))),
        )
        line_heights = [line.height for _text, _size, line, _is_line2 in lines]
        for index, (text, requested_size, line, is_line2) in enumerate(lines):
            line_left = left + (line2_indent if is_line2 else 0)
            if shadow_enabled and shadow_offset:
                shadow = title_line_for_width(
                    text,
                    title_font,
                    requested_size,
                    max_width,
                    outline,
                    title_bold,
                    title_italic,
                    fill="black",
                    stroke_fill="black",
                )
                image.paste(shadow, (line_left + shadow_offset, top + shadow_offset), shadow)
            image.paste(line, (line_left, top), line)
            top += line_heights[index] + line_gap

    # Icon 1 is the left icon and icon 2 is anchored to the lower-right edge.
    icons = [
        icon for icon in (
            load_cover_icon(str(cover.get("icon1_path") or "")),
            load_cover_icon(str(cover.get("icon2_path") or "")),
        )
        if icon is not None
    ]
    right = width - COVER_ICON_GAP_PX
    bottom = height - COVER_ICON_GAP_PX
    for icon in reversed(icons):
        right -= icon.width
        image.paste(icon, (right, bottom - icon.height), icon)
        right -= COVER_ICON_GAP_PX

    return image.convert("RGB")


def load_and_compose_cover_image(image_path: Optional[str], cover: Dict[str, Any]) -> Tuple[Image.Image, bool]:
    if image_path and Path(image_path).exists():
        with Image.open(image_path) as source:
            return compose_cover_image(source, cover), False
    return compose_cover_image(Image.new("RGB", PREVIEW_PLACEHOLDER_SIZE, "white"), cover), True


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
        self._render_preview_requested = False
        self._render_preview_after_id: Optional[str] = None
        self.video_jobs: Dict[str, VideoJob] = {}
        self.job_lock = threading.Lock()
        self.reserved_output_paths: set[str] = set()
        self._suppress_var_events = False
        self._suppress_cover_events = False
        self.icon_paths: Dict[int, str] = {}
        self.language_var = tk.StringVar(value="日本語")
        self.image_var = tk.StringVar(value=self.tr("unset"))
        self.audio_var = tk.StringVar(value=self.tr("unset"))
        self.srt_var = tk.StringVar(value=self.tr("unset"))
        self.output_var = tk.StringVar(value=self.tr("unset_output"))
        self.i18n_widgets: List[Tuple[Any, str, str]] = []
        self.file_row_labels: Dict[str, Any] = {}
        self.file_value_entries: Dict[str, ttk.Entry] = {}

        self.setup_style()
        self.build_ui()
        self.refresh_all_preset_combo()
        self.render_panel()
        self.update_status()
        self.root.after(100, self.process_log_queue)
        self.request_render_preview(delay_ms=250)

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
        return [labels[6], labels[10], labels[2]]

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
        style.configure("Path.TEntry", fieldbackground="#111214", foreground=self.fg, insertcolor=self.fg)
        style.map(
            "Path.TEntry",
            fieldbackground=[("readonly", "#111214"), ("focus", "#111214")],
            foreground=[("readonly", self.fg), ("focus", self.fg), ("disabled", "#777777")],
        )
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

    def editable_entry(self, parent, **kwargs):
        return tk.Entry(
            parent,
            bg="#111214",
            fg=self.fg,
            insertbackground=self.fg,
            selectbackground=self.accent,
            selectforeground="#FFFFFF",
            highlightthickness=1,
            highlightbackground="#56585d",
            highlightcolor=self.accent,
            relief=tk.SOLID,
            bd=1,
            **kwargs,
        )

    def editable_spinbox(self, parent, **kwargs):
        return tk.Spinbox(
            parent,
            bg="#111214",
            fg=self.fg,
            insertbackground=self.fg,
            selectbackground=self.accent,
            selectforeground="#FFFFFF",
            buttonbackground="#d8d6d0",
            highlightthickness=1,
            highlightbackground="#56585d",
            highlightcolor=self.accent,
            relief=tk.SOLID,
            bd=1,
            **kwargs,
        )

    def build_ui(self):
        main = ttk.Frame(self.root)
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # The quick panel occupies the entire left edge. The workspace on its
        # right owns both the preview row and the MP4 jobs / log row.
        self.left = ttk.Frame(main, style="Panel.TFrame")
        self.left.pack(side=tk.LEFT, fill=tk.Y)

        workspace = ttk.Frame(main)
        workspace.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0))

        top = ttk.Frame(workspace)
        top.pack(fill=tk.BOTH, expand=True)

        self.right = ttk.Frame(top, style="Panel.TFrame")
        self.right.pack(side=tk.RIGHT, fill=tk.Y)

        self.center = ttk.Frame(top)
        self.center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 8))

        self.build_left_panel()
        self.build_center_preview()
        self.build_right_controls()
        self.build_bottom(workspace)

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
        self.panel_edit_button = self.register_i18n(ttk.Button(name_frame, command=self.open_panel_editor), "panel_edit")
        self.panel_edit_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))
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

        self.build_cover_controls()

    def build_cover_controls(self):
        cover = get_cover_settings(self.store.settings())
        section = self.register_i18n(ttk.LabelFrame(self.left, style="Panel.TLabelframe"), "cover_section")
        section.pack(fill=tk.X, padx=8, pady=(0, 8))

        self._suppress_cover_events = True
        self.title_font_var = tk.StringVar(value=str(cover["title_font"]))
        self.title_bold_var = tk.BooleanVar(value=bool(cover["title_bold"]))
        self.title_italic_var = tk.BooleanVar(value=bool(cover["title_italic"]))
        self.title_color_var = tk.StringVar(value=normalize_cover_color(cover.get("title_color")))
        self.title_line1_var = tk.StringVar(value=str(cover["title_line1"]))
        self.title_line2_var = tk.StringVar(value=str(cover["title_line2"]))
        self.title_line1_size_var = tk.StringVar(value=str(cover["title_line1_size"]))
        self.title_line2_size_var = tk.StringVar(value=str(cover["title_line2_size"]))
        self.title_outline_var = tk.StringVar(value=str(cover["title_outline"]))
        self.title_shadow_enabled = tk.BooleanVar(value=bool(cover["title_shadow_enabled"]))
        self.title_shadow_offset_var = tk.StringVar(value=str(cover["title_shadow_offset"]))
        self.title_x_var = tk.IntVar(value=max(0, min(100, parse_cover_int(cover["title_x_pct"], 3))))
        self.title_y_var = tk.IntVar(value=max(0, min(100, parse_cover_int(cover["title_y_pct"], 3))))
        self.title_line_gap_var = tk.StringVar(value=str(cover["title_line_gap"]))
        self.title_line2_indent_var = tk.StringVar(value=str(cover["title_line2_indent"]))
        self.icon_paths = {
            1: str(cover.get("icon1_path") or ""),
            2: str(cover.get("icon2_path") or ""),
        }
        self.icon1_var = tk.StringVar(value=self.short_path(self.icon_paths[1]) if self.icon_paths[1] else self.tr("unset"))
        self.icon2_var = tk.StringVar(value=self.short_path(self.icon_paths[2]) if self.icon_paths[2] else self.tr("unset"))
        self._suppress_cover_events = False

        self.add_cover_position_slider(section, "title_x", self.title_x_var)
        self.add_cover_position_slider(section, "title_y", self.title_y_var)
        self.add_cover_combo_row(section, "title_font", self.title_font_var, self.available_font_families(), "title_font_combo", editable=True)
        style_row = ttk.Frame(section, style="Panel.TFrame")
        style_row.pack(fill=tk.X, padx=6, pady=2)
        bold_check = self.register_i18n(ttk.Checkbutton(style_row, variable=self.title_bold_var), "title_bold")
        bold_check.pack(side=tk.LEFT)
        italic_check = self.register_i18n(ttk.Checkbutton(style_row, variable=self.title_italic_var), "title_italic")
        italic_check.pack(side=tk.LEFT, padx=(10, 0))
        self.title_color_button = self.register_i18n(
            tk.Button(style_row, command=self.select_title_color, relief=tk.RAISED, bd=1, padx=6),
            "title_color",
        )
        self.title_color_button.pack(side=tk.LEFT, padx=(10, 0))
        self.update_title_color_button()
        self.add_cover_entry_row(section, "title_line1", self.title_line1_var)
        self.add_cover_compact_entry_row(section, "title_size", self.title_line1_size_var)
        self.add_cover_entry_row(section, "title_line2", self.title_line2_var)
        self.add_title_line2_size_row(section)
        self.add_cover_compact_entry_row(section, "title_outline", self.title_outline_var)

        shadow_row = ttk.Frame(section, style="Panel.TFrame")
        shadow_row.pack(fill=tk.X, padx=6, pady=2)
        shadow_label = self.register_i18n(ttk.Label(shadow_row, style="Panel.TLabel", width=15), "title_shadow")
        shadow_label.pack(side=tk.LEFT)
        ttk.Checkbutton(shadow_row, variable=self.title_shadow_enabled).pack(side=tk.LEFT)
        offset_label = self.register_i18n(ttk.Label(shadow_row, style="Panel.TLabel", width=16), "title_shadow_offset")
        offset_label.pack(side=tk.LEFT, padx=(8, 2))
        self.editable_entry(shadow_row, textvariable=self.title_shadow_offset_var, width=5).pack(side=tk.LEFT)

        self.add_cover_icon_row(section, 1)
        self.add_cover_icon_row(section, 2)

        for var in [
            self.title_font_var,
            self.title_bold_var,
            self.title_italic_var,
            self.title_color_var,
            self.title_line1_var,
            self.title_line2_var,
            self.title_line1_size_var,
            self.title_line2_size_var,
            self.title_outline_var,
            self.title_shadow_enabled,
            self.title_shadow_offset_var,
            self.title_x_var,
            self.title_y_var,
            self.title_line_gap_var,
            self.title_line2_indent_var,
        ]:
            var.trace_add("write", lambda *_args: self.on_cover_var_changed())

    def add_cover_combo_row(self, parent, label_key: str, value_var: tk.StringVar, values: List[str], attr_name: str, editable: bool = False):
        frame = ttk.Frame(parent, style="Panel.TFrame")
        frame.pack(fill=tk.X, padx=6, pady=2)
        label = self.register_i18n(ttk.Label(frame, style="Panel.TLabel", width=15), label_key)
        label.pack(side=tk.LEFT)
        combo = ttk.Combobox(
            frame,
            textvariable=value_var,
            values=values,
            state="normal" if editable else "readonly",
            style="Readable.TCombobox",
        )
        combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        setattr(self, attr_name, combo)

    def add_cover_entry_row(self, parent, label_key: str, value_var: tk.StringVar):
        frame = ttk.Frame(parent, style="Panel.TFrame")
        frame.pack(fill=tk.X, padx=6, pady=2)
        label = self.register_i18n(ttk.Label(frame, style="Panel.TLabel", width=15), label_key)
        label.pack(side=tk.LEFT)
        self.editable_entry(frame, textvariable=value_var).pack(side=tk.LEFT, fill=tk.X, expand=True)

    def add_cover_compact_entry_row(self, parent, label_key: str, value_var: tk.StringVar):
        frame = ttk.Frame(parent, style="Panel.TFrame")
        frame.pack(fill=tk.X, padx=6, pady=2)
        label = self.register_i18n(ttk.Label(frame, style="Panel.TLabel", width=15), label_key)
        label.pack(side=tk.LEFT)
        self.editable_entry(frame, textvariable=value_var, width=8).pack(side=tk.LEFT)

    def add_title_line2_size_row(self, parent):
        frame = ttk.Frame(parent, style="Panel.TFrame")
        frame.pack(fill=tk.X, padx=6, pady=2)
        size_label = self.register_i18n(ttk.Label(frame, style="Panel.TLabel", width=13), "title_size")
        size_label.pack(side=tk.LEFT)
        self.editable_entry(frame, textvariable=self.title_line2_size_var, width=5).pack(side=tk.LEFT)
        gap_label = self.register_i18n(ttk.Label(frame, style="Panel.TLabel"), "title_line_gap")
        gap_label.pack(side=tk.LEFT, padx=(10, 2))
        self.editable_entry(frame, textvariable=self.title_line_gap_var, width=4).pack(side=tk.LEFT)
        indent_label = self.register_i18n(ttk.Label(frame, style="Panel.TLabel"), "title_line2_indent")
        indent_label.pack(side=tk.LEFT, padx=(8, 2))
        self.editable_spinbox(
            frame,
            from_=-COVER_TITLE_LINE2_INDENT_LIMIT_PX,
            to=COVER_TITLE_LINE2_INDENT_LIMIT_PX,
            textvariable=self.title_line2_indent_var,
            width=5,
        ).pack(side=tk.LEFT)

    def add_cover_position_slider(self, parent, label_key: str, value_var: tk.IntVar):
        frame = ttk.Frame(parent, style="Panel.TFrame")
        frame.pack(fill=tk.X, padx=6, pady=2)
        label = self.register_i18n(ttk.Label(frame, style="Panel.TLabel", width=15), label_key)
        label.pack(side=tk.LEFT)
        scale = tk.Scale(
            frame,
            variable=value_var,
            from_=0,
            to=100,
            resolution=1,
            orient=tk.HORIZONTAL,
            showvalue=False,
            highlightthickness=0,
            bg=self.panel_bg,
            fg=self.fg,
            activebackground=self.accent,
            troughcolor="#111214",
            bd=0,
        )
        scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(frame, textvariable=value_var, style="Panel.TLabel", width=4, anchor=tk.E).pack(side=tk.LEFT)

    def add_cover_icon_row(self, parent, icon_number: int):
        frame = ttk.Frame(parent, style="Panel.TFrame")
        frame.pack(fill=tk.X, padx=6, pady=2)
        label = self.register_i18n(ttk.Label(frame, style="Panel.TLabel", width=15), f"icon{icon_number}")
        label.pack(side=tk.LEFT)
        value_var = self.icon1_var if icon_number == 1 else self.icon2_var
        entry = ttk.Entry(frame, textvariable=value_var, state="readonly", style="Path.TEntry")
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        value_var.trace_add("write", lambda *_args, target=entry: self.root.after_idle(lambda: self.scroll_entry_to_tail(target)))
        self.root.after_idle(lambda target=entry: self.scroll_entry_to_tail(target))
        select_button = self.register_i18n(ttk.Button(frame, command=lambda n=icon_number: self.select_cover_icon(n)), "select")
        select_button.pack(side=tk.LEFT)
        clear_button = self.register_i18n(ttk.Button(frame, command=lambda n=icon_number: self.clear_cover_icon(n)), "clear")
        clear_button.pack(side=tk.LEFT, padx=(3, 0))

    def cover_settings_snapshot(self) -> Dict[str, Any]:
        cover = dict(DEFAULT_COVER_SETTINGS)
        if not hasattr(self, "title_line1_var"):
            cover.update(get_cover_settings(self.store.settings()))
            return cover
        cover.update({
            "title_font": self.title_font_var.get().strip() or DEFAULT_PREVIEW_FONT,
            "title_bold": bool(self.title_bold_var.get()),
            "title_italic": bool(self.title_italic_var.get()),
            "title_color": normalize_cover_color(self.title_color_var.get()),
            "title_line1": self.title_line1_var.get(),
            "title_line2": self.title_line2_var.get(),
            "title_line1_size": max(1, self.parse_int(self.title_line1_size_var.get()) or DEFAULT_COVER_SETTINGS["title_line1_size"]),
            "title_line2_size": max(1, self.parse_int(self.title_line2_size_var.get()) or DEFAULT_COVER_SETTINGS["title_line2_size"]),
            "title_outline": max(0, self.parse_int(self.title_outline_var.get()) or 0),
            "title_shadow_enabled": bool(self.title_shadow_enabled.get()),
            "title_shadow_offset": max(0, self.parse_int(self.title_shadow_offset_var.get()) or 0),
            "title_x_pct": int(self.title_x_var.get()),
            "title_y_pct": int(self.title_y_var.get()),
            "title_line_gap": max(0, self.parse_int(self.title_line_gap_var.get()) or 0),
            "title_line2_indent": max(
                -COVER_TITLE_LINE2_INDENT_LIMIT_PX,
                min(COVER_TITLE_LINE2_INDENT_LIMIT_PX, self.parse_int(self.title_line2_indent_var.get()) or 0),
            ),
            "icon1_path": self.icon_paths.get(1, ""),
            "icon2_path": self.icon_paths.get(2, ""),
        })
        return json.loads(json.dumps(cover, ensure_ascii=False))

    def save_cover_settings(self):
        saved = get_cover_settings(self.store.settings())
        saved.update(self.cover_settings_snapshot())
        self.store.save()

    def on_cover_var_changed(self):
        if self._suppress_cover_events:
            return
        self.update_title_color_button()
        self.save_cover_settings()
        self.render_preview_path = None
        self.simple_preview()

    def update_title_color_button(self):
        if not hasattr(self, "title_color_button"):
            return
        color = normalize_cover_color(self.title_color_var.get())
        red = int(color[1:3], 16)
        green = int(color[3:5], 16)
        blue = int(color[5:7], 16)
        brightness = red * 0.299 + green * 0.587 + blue * 0.114
        foreground = "#111111" if brightness >= 160 else "#FFFFFF"
        self.title_color_button.configure(bg=color, fg=foreground, activebackground=color, activeforeground=foreground)

    def select_title_color(self):
        _rgb, color = colorchooser.askcolor(
            color=normalize_cover_color(self.title_color_var.get()),
            parent=self.root,
            title=self.tr("title_color"),
        )
        if color:
            self.title_color_var.set(normalize_cover_color(color))

    def select_cover_icon(self, icon_number: int):
        path = filedialog.askopenfilename(filetypes=[("Image", "*.png *.jpg *.jpeg"), ("All", "*.*")])
        if not path:
            return
        self.icon_paths[icon_number] = path
        value_var = self.icon1_var if icon_number == 1 else self.icon2_var
        value_var.set(self.short_path(path))
        self.save_cover_settings()
        self.render_preview_path = None
        self.simple_preview()

    def clear_cover_icon(self, icon_number: int):
        self.icon_paths[icon_number] = ""
        value_var = self.icon1_var if icon_number == 1 else self.icon2_var
        value_var.set(self.tr("unset"))
        self.save_cover_settings()
        self.render_preview_path = None
        self.simple_preview()

    def reset_title_from_audio(self, audio_path: str):
        if not hasattr(self, "title_line1_var"):
            return
        self._suppress_cover_events = True
        self.title_line1_var.set(Path(audio_path).stem)
        self.title_line2_var.set("")
        self._suppress_cover_events = False
        self.save_cover_settings()
        self.render_preview_path = None

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
        self.preview_text_entry = self.editable_entry(preview_text_frame, textvariable=self.preview_text_var)
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
        value_entry = ttk.Entry(frame, textvariable=var, state="readonly", justify=tk.LEFT, width=28, style="Path.TEntry")
        value_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        self.file_value_entries[label_key] = value_entry
        var.trace_add("write", lambda *_args, entry=value_entry: self.root.after_idle(lambda: self.scroll_entry_to_tail(entry)))
        self.root.after_idle(lambda entry=value_entry: self.scroll_entry_to_tail(entry))
        button = self.register_i18n(ttk.Button(frame, command=command), button_key)
        button.pack(side=tk.RIGHT)

    def scroll_entry_to_tail(self, entry: ttk.Entry):
        try:
            entry.xview_moveto(1.0)
        except tk.TclError:
            pass

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
        self.editable_entry(frame, textvariable=value_var, width=width).pack(side=tk.LEFT, fill=tk.X, expand=True)

    def add_plain_entry(self, label: str, value_var: tk.StringVar, width: int = 24):
        frame = ttk.Frame(self.right, style="Panel.TFrame")
        frame.pack(fill=tk.X, padx=8, pady=2)
        ttk.Label(frame, text="", style="Panel.TLabel", width=2).pack(side=tk.LEFT)
        ttk.Label(frame, text=label, style="Panel.TLabel", width=14).pack(side=tk.LEFT)
        self.editable_entry(frame, textvariable=value_var, width=width).pack(side=tk.LEFT, fill=tk.X, expand=True)

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
        bottom.grid_columnconfigure(0, weight=3)
        bottom.grid_columnconfigure(1, weight=2)
        bottom.grid_rowconfigure(0, weight=1)

        jobs_frame = ttk.Frame(bottom)
        jobs_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.jobs_label = self.register_i18n(ttk.Label(jobs_frame), "jobs")
        self.jobs_label.pack(anchor=tk.W)
        self.jobs_tree = ttk.Treeview(jobs_frame, columns=("status", "output"), show="headings", height=7)
        self.jobs_tree.heading("status", text=self.tr("job_status"))
        self.jobs_tree.heading("output", text=self.tr("job_output"))
        self.jobs_tree.column("status", width=110, minwidth=90, stretch=False)
        self.jobs_tree.column("output", width=260, minwidth=180, stretch=True)
        self.jobs_tree.pack(fill=tk.BOTH, expand=True)

        log_frame = ttk.Frame(bottom)
        log_frame.grid(row=0, column=1, sticky="nsew")
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
                    height=2,
                    bg=bg,
                    fg=fg,
                    activebackground="#4a4d55",
                    activeforeground=self.fg,
                    relief=tk.RAISED,
                    wraplength=90,
                    command=lambda pid=preset_id: self.apply_preset(pid, render=True) if pid else None,
                )
                btn.grid(row=r, column=c, padx=2, pady=2, sticky="nsew")
                if preset_id:
                    btn.tooltip = ToolTip(btn, full_name)
                    self.register_drop(btn, lambda event, pid=preset_id: self.handle_drop(event, preset_id=pid))

    def open_panel_editor(self):
        if not self.store.panel_pages:
            return
        if hasattr(self, "panel_editor_window") and self.panel_editor_window and self.panel_editor_window.winfo_exists():
            self.panel_editor_window.lift()
            self.panel_editor_window.focus_set()
            return

        win = tk.Toplevel(self.root)
        self.panel_editor_window = win
        self.panel_editor_page_index = self.current_page_index
        self.panel_editor_selected: Optional[Tuple[int, int]] = None
        self.panel_editor_buttons: Dict[int, tk.Button] = {}
        self.panel_editor_label_var = tk.StringVar()
        self.panel_editor_selected_var = tk.StringVar(value=f"{self.tr('selected_panel')} {self.tr('no_panel_selected')}")

        win.title(self.tr("panel_edit_title"))
        win.configure(bg=self.bg)
        win.transient(self.root)
        win.grab_set()
        win.protocol("WM_DELETE_WINDOW", self.close_panel_editor)

        outer = ttk.Frame(win, style="Panel.TFrame")
        outer.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Label(outer, text=self.tr("panel_edit_hint"), style="Panel.TLabel", wraplength=520, justify=tk.LEFT).pack(fill=tk.X)

        page_frame = ttk.Frame(outer, style="Panel.TFrame")
        page_frame.pack(fill=tk.X, pady=(8, 6))
        self.panel_editor_page_buttons = []
        for i in range(len(self.store.panel_pages)):
            btn = tk.Button(
                page_frame,
                text=self.page_display_name(self.store.panel_pages[i], i),
                command=lambda idx=i: self.set_panel_editor_page(idx),
                bg="#3a3d44",
                fg=self.fg,
                activebackground="#4a4d55",
                activeforeground=self.fg,
                relief=tk.FLAT,
            )
            btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
            self.panel_editor_page_buttons.append(btn)

        self.panel_editor_grid = ttk.Frame(outer, style="Panel.TFrame")
        self.panel_editor_grid.pack(fill=tk.BOTH, expand=True, pady=(2, 8))

        ttk.Label(outer, textvariable=self.panel_editor_selected_var, style="Panel.TLabel", foreground=self.muted).pack(anchor=tk.W)

        label_frame = ttk.Frame(outer, style="Panel.TFrame")
        label_frame.pack(fill=tk.X, pady=(6, 4))
        ttk.Label(label_frame, text=self.tr("panel_label"), style="Panel.TLabel", width=12).pack(side=tk.LEFT)
        self.panel_editor_label_entry = self.editable_entry(label_frame, textvariable=self.panel_editor_label_var)
        self.panel_editor_label_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self.panel_editor_label_entry.bind("<Return>", lambda _event: self.apply_panel_editor_label())
        ttk.Button(label_frame, text=self.tr("apply_panel_label"), command=self.apply_panel_editor_label).pack(side=tk.RIGHT)

        button_frame = ttk.Frame(outer, style="Panel.TFrame")
        button_frame.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(button_frame, text=self.tr("clear_panel_slot"), command=self.clear_panel_editor_slot).pack(side=tk.LEFT)
        ttk.Button(button_frame, text=self.tr("close"), command=self.close_panel_editor).pack(side=tk.RIGHT)

        self.render_panel_editor()
        win.update_idletasks()
        win.minsize(max(560, win.winfo_reqwidth()), win.winfo_reqheight())

    def close_panel_editor(self):
        if hasattr(self, "panel_editor_window") and self.panel_editor_window and self.panel_editor_window.winfo_exists():
            try:
                self.panel_editor_window.grab_release()
            except tk.TclError:
                pass
            self.panel_editor_window.destroy()

    def set_panel_editor_page(self, index: int):
        self.panel_editor_page_index = index
        self.render_panel_editor()

    def render_panel_editor(self):
        if not hasattr(self, "panel_editor_grid"):
            return
        for child in self.panel_editor_grid.winfo_children():
            child.destroy()
        self.panel_editor_buttons = {}
        page_index = self.panel_editor_page_index
        page = self.store.panel_pages[page_index]
        rows = int(page.get("rows", 5))
        cols = int(page.get("cols", 4))
        slot_map = {int(s.get("slot", 0)): s for s in page.get("slots", [])}

        for i, btn in enumerate(getattr(self, "panel_editor_page_buttons", [])):
            btn.config(
                text=self.page_display_name(self.store.panel_pages[i], i),
                bg=self.accent if i == page_index else "#3a3d44",
            )

        selected = getattr(self, "panel_editor_selected", None)
        for r in range(rows):
            self.panel_editor_grid.grid_rowconfigure(r, weight=1)
            for c in range(cols):
                self.panel_editor_grid.grid_columnconfigure(c, weight=1)
                slot_no = r * cols + c + 1
                slot = slot_map.get(slot_no)
                label = self.tr("empty_slot") if not slot else self.slot_display_label(slot)
                preset_id = None if not slot else slot.get("preset_id")
                is_selected = selected == (page_index, slot_no)
                bg = self.accent if is_selected else ("#343842" if preset_id else "#24262b")
                fg = self.fg if preset_id or is_selected else "#777"
                btn = tk.Button(
                    self.panel_editor_grid,
                    text=label,
                    width=12,
                    height=3,
                    bg=bg,
                    fg=fg,
                    activebackground="#4a4d55",
                    activeforeground=self.fg,
                    relief=tk.RAISED,
                    wraplength=90,
                    command=lambda s=slot_no: self.on_panel_editor_slot_clicked(s),
                )
                btn.grid(row=r, column=c, padx=3, pady=3, sticky="nsew")
                self.panel_editor_buttons[slot_no] = btn
        self.refresh_panel_editor_selection()

    def on_panel_editor_slot_clicked(self, slot_no: int):
        page_index = self.panel_editor_page_index
        selected = getattr(self, "panel_editor_selected", None)
        slot = self.store.slot_by_number(page_index, slot_no)
        if selected:
            source_page, source_slot = selected
            if (source_page, source_slot) == (page_index, slot_no):
                self.panel_editor_selected = None
                self.render_panel_editor()
                return
            if self.store.move_or_swap_slot(source_page, source_slot, page_index, slot_no):
                self.panel_editor_selected = None
                self.render_panel()
                self.render_panel_editor()
            return
        if slot:
            self.panel_editor_selected = (page_index, slot_no)
            self.refresh_panel_editor_selection()
            self.render_panel_editor()

    def refresh_panel_editor_selection(self):
        selected = getattr(self, "panel_editor_selected", None)
        if not selected:
            if hasattr(self, "panel_editor_selected_var"):
                self.panel_editor_selected_var.set(f"{self.tr('selected_panel')} {self.tr('no_panel_selected')}")
            if hasattr(self, "panel_editor_label_var"):
                self.panel_editor_label_var.set("")
            return
        page_index, slot_no = selected
        slot = self.store.slot_by_number(page_index, slot_no)
        if not slot:
            self.panel_editor_selected = None
            self.refresh_panel_editor_selection()
            return
        page_name = self.page_display_name(self.store.panel_pages[page_index], page_index)
        preset_name = self.label_for_preset(slot.get("preset_id"))
        self.panel_editor_selected_var.set(f"{self.tr('selected_panel')} {page_name} #{slot_no}: {preset_name}")
        self.panel_editor_label_var.set(self.slot_display_label(slot))

    def apply_panel_editor_label(self):
        selected = getattr(self, "panel_editor_selected", None)
        if not selected:
            return
        page_index, slot_no = selected
        slot = self.store.slot_by_number(page_index, slot_no)
        if not slot:
            return
        label = self.panel_editor_label_var.get().strip()
        if not label:
            label = self.label_for_preset(slot.get("preset_id"))
        self.store.set_slot_label(page_index, slot_no, localized_record(label, self.language_code(), slot.get("label")))
        self.panel_editor_selected = None
        self.render_panel()
        self.render_panel_editor()

    def clear_panel_editor_slot(self):
        selected = getattr(self, "panel_editor_selected", None)
        if not selected:
            return
        page_index, slot_no = selected
        if self.store.clear_slot(page_index, slot_no):
            self.panel_editor_selected = None
            self.render_panel()
            self.render_panel_editor()

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
        self.request_render_preview()

    def set_audio(self, path: str, auto_srt: bool = True, auto_image: bool = False):
        audio_changed = self.audio_path != path
        self.audio_path = path
        self.audio_var.set(self.short_path(path))
        self.log(f"音源を設定: {path}")
        if audio_changed:
            self.reset_title_from_audio(path)
            self.simple_preview()
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
                self.set_srt(srt, auto=True, auto_audio=False, auto_image=False)
            else:
                self.log("同名SRTは見つかりませんでした。字幕を付ける場合は手動で選択してください。")
        self.update_output_candidate()
        self.request_render_preview()

    def set_srt(self, path: str, auto: bool = False, auto_audio: bool = True, auto_image: bool = True):
        self.srt_path = path
        self.srt_var.set(self.short_path(path))
        self.log(("同名SRTを自動設定: " if auto else "SRTを設定: ") + path)
        if not auto and auto_image:
            title_image = sibling_title_image_for_path(path)
            if title_image:
                self.set_image(title_image)
                self.log(f"SRT名_title.png を自動設定: {title_image}")
        if not auto and auto_audio:
            audio = sibling_audio_for_srt(path)
            if audio:
                self.set_audio(audio, auto_srt=False, auto_image=False)
                self.log(f"同名音源を自動設定: {audio}")
        self.set_longest_srt_preview_text()
        self.request_render_preview()

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
            self.set_srt(srts[0], auto_audio=not bool(audios), auto_image=not bool(images))  # explicit drop overrides auto-detected SRT
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
            img = compose_cover_image(img, self.cover_settings_snapshot())
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
            self._render_preview_requested = True
            self.log("レンダープレビュー生成中です。完了後に最新設定で更新します。")
            return
        style = self.vars_to_style()
        text = self.preview_text_var.get() or srt_preview_text(self.srt_path, self.preview_placeholder_text())
        image_path = self.image_path if self.image_path and Path(self.image_path).exists() else None
        cover_settings = self.cover_settings_snapshot()
        self.preview_status_var.set(self.tr("rendering_preview"))
        self.render_thread = threading.Thread(target=self._render_preview_worker, args=(style, text, image_path, cover_settings), daemon=True)
        self.render_thread.start()

    def request_render_preview(self, delay_ms: int = 0):
        if self._render_preview_after_id:
            self.root.after_cancel(self._render_preview_after_id)
        self._render_preview_after_id = self.root.after(delay_ms, self._run_requested_render_preview)

    def _run_requested_render_preview(self):
        self._render_preview_after_id = None
        self.render_preview()

    def _render_preview_worker(self, style: Dict[str, Any], text: str, image_path: Optional[str], cover_settings: Dict[str, Any]):
        try:
            with tempfile.TemporaryDirectory(prefix="subtitle_preview_") as td:
                input_image = str(Path(td) / "cover.png")
                cover_image, _placeholder = load_and_compose_cover_image(image_path, cover_settings)
                cover_image.save(input_image)
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
            self.call_ui_thread(self._render_preview_failed)

    def _render_preview_done(self):
        try:
            img = Image.open(self.render_preview_path).convert("RGB")
            self.display_image(img)
            self.preview_status_var.set(self.tr("render_preview_done"))
            self.update_status()
        except Exception as exc:
            self.log(f"レンダープレビュー表示失敗: {exc}")
        self._run_queued_render_preview()

    def _render_preview_failed(self):
        self.preview_status_var.set(self.tr("render_preview_failed"))
        self._run_queued_render_preview()

    def _run_queued_render_preview(self):
        if not self._render_preview_requested:
            return
        if self.render_thread and self.render_thread.is_alive():
            self.root.after(50, self._run_queued_render_preview)
            return
        self._render_preview_requested = False
        self.render_preview()

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
        if not self.image_path or not Path(self.image_path).is_file():
            missing.append("画像")
        if not self.audio_path or not Path(self.audio_path).is_file():
            missing.append("音源")
        if missing:
            messagebox.showerror("入力不足", "未設定: " + ", ".join(missing))
            return
        output_path = self.reserve_output_path()
        if not output_path:
            return
        style = json.loads(json.dumps(self.vars_to_style(), ensure_ascii=False))
        cover_settings = self.cover_settings_snapshot()
        job = VideoJob(
            id=uuid.uuid4().hex,
            image_path=self.image_path,
            audio_path=self.audio_path,
            srt_path=self.srt_path,
            output_path=output_path,
            style=style,
            cover_settings=cover_settings,
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
                work_cover = str(td_path / "cover.png")
                cover_image, _placeholder = load_and_compose_cover_image(job.image_path, job.cover_settings)
                cover_image.save(work_cover)
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
                    work_cover,
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
            duration = float(proc.stdout.strip())
        except Exception:
            raise RuntimeError("ffprobeから音声長を取得できませんでした。")
        if not duration > 0:
            raise RuntimeError(f"音声長が不正です: {duration}")
        return duration

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
    root.geometry("1480x860")
    app = App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
