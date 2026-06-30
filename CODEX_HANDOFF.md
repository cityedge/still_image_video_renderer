# Codex引継ぎメモ：Still Image Video Renderer

## 1. 現在位置

このプロジェクトは、既存の多数のffmpeg用バッチファイルを置き換えるためのPython/Tkinterプロトタイプです。
目的は、静止画像、SRT字幕、MP3/WAV音源を合成し、静止画背景に字幕を焼き込んだMP4動画を作ることです。

現行コードは `subtitle_image_mp4_maker.py` です。バージョン表記は `0.2.0` です。
ユーザー環境で起動・基本動作は確認済みです。ただし、この版はGUIプロトタイプであり、今後の主作業はGUI/UX改善です。

## 2. プロトタイプで実装済みの機能

- TkinterベースのダークテーマGUI。
- 主要UIラベルは日本語/English切替式。
- `tkinterdnd2` によるドラッグ＆ドロップ。
- 4列×5行のクイックパネルを2ページ持つ。
- クイックパネルは左側配置。ページ1に通常用とショート用、ページ2は初期空き。
- クイックパネルはマウスオーバーでプリセットのフルネームをツールチップ表示する。
- クイックパネル選択時、全プリセットコンボも同期する。
- パネルの各スロットにプリセットを割り当てる。
- パネルへ画像・音源・SRTをドロップすると、そのパネルのプリセットを適用する。
- 汎用ドロップエリアに画像・音源・SRTをドロップできる。
- 画像、音源、SRTの個別選択ボタンあり。
- 音源と同名の `.srt` を自動検出する。
- 音源のみドロップした場合、同じフォルダの `<音源名>_title.png` を自動検出する。
- 出力ファイル名候補は音源名ベースの `<音源名>.mp4`。重複時は `_001` などを付ける。
- `ffmpeg` 実レンダーによる1枚プレビューを生成する。
- 値を手作業編集している間はPillowによる簡易プレビューを出す。
- 画像未指定時も白い16:9背景で簡易/レンダープレビュー可能。
- Alignmentは `6（中央上）` / `10（中央）` の二択UI。
- 字幕サイズは `-5`, `-1`, `+1`, `+5` ボタンで微調整可能。
- `fontname`、`fontsize`、`alignment`、`margin_v` は `null` 許容。
- `null` の字幕スタイル項目は `force_style` へ出さない。
- 現在設定を新規プリセットとして保存できる。
- 選択中プリセットへの上書き保存ができる。
- `MP4作成` はジョブ化済み。ボタン押下時点の入力と字幕設定を固定し、ffmpeg実行中でも次の作業を続けられる。
- `ffmpeg.exe` / `ffprobe.exe` は `bin`、アプリ直下、PATHの順で探す。
- PyInstaller用バッチに `--collect-data tkinterdnd2` を入れている。

## 3. 実行方法

### 開発実行

```bat
run_dev.bat
```

または、仮想環境を作成後に直接実行します。

```bat
py -3.10 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe subtitle_image_mp4_maker.py
```

`ffmpeg.exe` と `ffprobe.exe` は、以下のどれかに置いてください。

1. アプリフォルダ直下の `bin` フォルダ
2. アプリフォルダ直下
3. PATH上

推奨構成：

```text
project/
  subtitle_image_mp4_maker.py
  presets.json          ← 初回起動時に自動生成
  bin/
    ffmpeg.exe
    ffprobe.exe
```

### EXE化

```bat
build_exe_onedir.bat
```

`tkinterdnd2` はTcl/Tk側のデータを必要とするため、PyInstallerでは `--collect-data tkinterdnd2` が必要です。現行バッチにはこの指定を入れています。
ビルドバッチは `.venv\Scripts\python.exe` を直接使います。
onedir配布名は `StillImageVideoRenderer` です。

## 4. 重要な設計方針

### 4.1 プリセットは単一モデル

通常用、ショート用、センター用、MarginV用などを別モデルに分けないでください。
プリセットは単に `force_style` に出す可能性のある値の集合です。
指定しない項目は `null` にします。

```json
{
  "id": "normal_slightly_up_v95",
  "name": {
    "ja": "04 通常 字幕やや上 v95",
    "en": "04 Normal Slightly Up v95"
  },
  "tags": ["normal"],
  "style": {
    "fontname": "UD デジタル 教科書体 NK",
    "fontsize": 20,
    "alignment": 6,
    "margin_v": 95
  }
}
```

`name` とクイックパネルスロットの `label` は `ja` / `en` の言語別表示名を持ちます。片方は `null` を許し、現在のUI言語側が空ならもう一方へフォールバックします。

フォント未指定のショート系は次のように表現します。

```json
{
  "id": "short_slightly_up_v90",
  "name": "14 ショート 字幕やや上 v90",
  "tags": ["short"],
  "style": {
    "fontname": null,
    "fontsize": null,
    "alignment": 6,
    "margin_v": 90
  }
}
```

この場合、ffmpegへ出す `force_style` は次のようになります。

```text
alignment=6,MarginV=90
```

### 4.2 `alignment=10` と `MarginV` は同時指定可能にする

`alignment=10` を「センター専用モード」として特別扱いしないでください。
`alignment=10,MarginV=40` のようなプリセットも将来的にあり得ます。
この場合、センター基準から下方向にずれる挙動になり、2行字幕時の挙動が `alignment=6` 系とは異なります。

### 4.3 `MarginV=null` と `MarginV=0` は別物として扱う

既存の `01_通常_字幕上部_v0` は、もとのバッチでは `alignment=6,` という末尾カンマ付きでした。
ffmpegでは動作していますが、Python版では末尾カンマを削除し、`alignment=6` のみを出します。
`MarginV=0` を勝手に追加しないでください。

### 4.4 プリセットと現在作成設定を分離する

プリセットを選択したら、その内容を「現在の作成設定」にコピーします。
メイン画面でフォント名、フォントサイズ、Alignment、MarginVを変えても、元プリセットは即座には変更しません。
保存操作をしたときだけ、新規プリセット追加または既存プリセット上書きを行います。

### 4.5 レンダープレビューを正とする

Pillow/Tkinterの簡易プレビューは、ffmpeg/libassとフォントサイズ・位置が一致しません。
最終判断は必ずffmpegレンダープレビューで行います。

プロトタイプでは以下のルールです。

- パネルドロップ時：ffmpegレンダープレビューを自動生成。
- 汎用ドロップ後にプリセット適用：ffmpegレンダープレビューを生成。
- 手作業で値を変更中：Pillow簡易プレビュー。
- `レンダープレビュー更新` ボタン：ffmpeg実レンダーへ戻す。

## 5. 既知の課題・次にやるべきこと

### 5.1 GUI/UX改善が最優先

このアプリはffmpegラッパーですが、乗り換え価値はGUIにあります。
次の点を優先してください。

- 右ペインの入力ファイル表示が長いファイル名で窮屈になりやすい。
- 画面幅が狭いとプレビューと右ペインのバランスが崩れやすい。
- パネルスロットの編集機能が弱い。割り当て変更、解除、表示名変更が必要。
- ページ名変更はあるが、ページ編集UIは最低限。
- 全プリセット選択は現在コンボボックスのみ。検索付きUIにしたい。
- 現在設定の `null` 切替UIはチェックボックス方式だが、もう少し分かりやすくしたい。

### 5.2 プレビュー改善

- 簡易プレビューはまだ粗い。
- 現在の補正係数は `preview_font_scale=0.76`。
- フォント未指定時は `16 × 画像高さ / 288 × preview_font_scale` で推定。
- フォント指定ありは `fontsize × 画像高さ / 288 × preview_font_scale` で推定。
- 実用上はレンダープレビューが正なので、簡易プレビューは「編集中の目安」と割り切る。

将来案：

- 値変更後0.5〜0.8秒程度のデバウンスで自動レンダープレビュー更新。
- 前回レンダープレビュー上にガイド線だけ重ねる方式。
- preview_font_scaleを設定画面から変更可能にする。

### 5.3 出力解像度と画像フィット

現行版は、もとのバッチと同じく画像サイズそのままです。
ffmpeg側で `scale=trunc(iw/2)*2:trunc(ih/2)*2` の偶数化だけを行います。

将来必要になり得る機能：

- 1280×720
- 1920×1080
- 720×1280
- 1024×1024
- contain / cover / stretch

ただし、初期段階では実装を急がないでください。

### 5.4 MP4生成の進捗表示

現行版はMP4ジョブ一覧とログ表示のみです。
将来はffmpegの進捗をパースして、簡単な進捗バーを付けるとよいです。
ジョブは投入時点で画像、音源、SRT、出力先、字幕スタイルをスナップショットします。
実行中ジョブは `self.image_path` などの現在UI状態を参照しない方針を維持してください。
自動出力候補は実行中ジョブの予約済み出力先も考慮します。

### 5.5 エラー処理

- ffmpegの失敗ログをユーザー向けに整理したい。
- SRTの文字コードエラー、パスエラー、フォント未検出などを分かりやすく出したい。
- 日本語パスでの動作は設計上想定しているが、EXE版で改めて確認すること。

## 6. 既存プリセット

現在の初期プリセットは `presets_default.json` にも出力しています。
もとのバッチの該当行は `docs/original_batch_presets.txt` に保存しています。

構成は概ね以下です。

- ページ1初期配置：通常系プリセットとショート系プリセット
- ページ2初期配置：空き

ただし、ページ1/ページ2は固定意味を持ちません。
ユーザーはページ1に通常・ショート混在、ページ2にマイナー設定、という運用を想定しています。

## 7. コード上の注目箇所

- `DEFAULT_PRESETS`: 初期プリセットと初期パネル配置。
- `PresetStore`: `presets.json` のロード、保存、マイグレーション。
- `style_to_force_style()`: `null` を除外してffmpeg用の `force_style` を組み立てる。
- `make_subtitle_filter()`: subtitlesフィルター文字列を作る。
- `sibling_srt_for_audio()`: 音源と同名SRTの自動検出。
- `sibling_title_image_for_audio()`: `<音源名>_title.png` の自動検出。
- `handle_drop()`: ドロップ時のファイル分類とプリセット適用。
- `simple_preview()`: Pillow簡易プレビュー。
- `_render_preview_worker()`: ffmpeg実レンダープレビュー。
- `VideoJob`: MP4作成ジョブのスナップショット。
- `_create_mp4_worker()`: 実際のMP4作成。必ず `VideoJob` の値だけを参照し、UIの現在値を参照しない。

## 8. 開発時の注意

- GUIは日本語・英語併記の方針。
- ダークテーマ維持。
- `--windowed` EXEでffmpeg/ffprobe呼び出し時に黒いコンソール窓が出ないよう、`startupinfo_no_window()` と `creationflags_no_window()` を維持する。
- subprocessは `run_subprocess()` または `popen_subprocess()` を使い、Windowsでは `subprocess_no_window_kwargs()` 経由で `CREATE_NO_WINDOW` 相当を適用する。
- `--onedir` 配布を推奨。ffmpeg/ffprobe同梱と相性がよい。
- `--onefile` は、tkinterdnd2とffmpeg同梱の扱いが複雑になるため、現時点では推奨しない。
