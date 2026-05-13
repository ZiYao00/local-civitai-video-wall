# -*- coding: utf-8 -*-
r"""
Local Civitai-style Video Wall v2

Usage:
1. Make sure Python 3.9+ is installed.
2. Double-click start.bat, or run:
   python app.py
3. Open:
   http://127.0.0.1:8787

v2 changes:
- Path input is empty by default.
- Manual path input.
- Windows folder picker button.
- Remember path checkbox.
- Recursive scan checkbox.
- Adjustable columns: 4 / 5 / 6 / 7 / 8 / 9.
- Playback limit: 12 / 18 / 24 / 30.
- Compact topbar and immersive mode.
"""

from __future__ import annotations

import json
import mimetypes
import os
import posixpath
import re
import subprocess
import sys
import threading
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, unquote, quote

HOST = "127.0.0.1"
PORT = 8787

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
CONFIG_FILE = BASE_DIR / "config.json"

VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v"}

DEFAULT_CONFIG = {
    "remember_path": False,
    "last_video_dir": "",
    "recursive": False,
    "columns": 6,
    "play_limit": 24,
    "sort_mode": "mtime_desc",
    "immersive": False,
}

runtime_lock = threading.Lock()
runtime_video_dir = ""


def normalize_path(p: str) -> str:
    p = (p or "").strip().strip('"')
    return str(Path(p).expanduser()) if p else ""


def clamp_int(value, default: int, low: int, high: int) -> int:
    try:
        n = int(value)
    except Exception:
        n = default
    return max(low, min(high, n))


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return dict(DEFAULT_CONFIG)
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return dict(DEFAULT_CONFIG)
    cfg = dict(DEFAULT_CONFIG)
    cfg.update({k: data.get(k, v) for k, v in DEFAULT_CONFIG.items()})
    if not cfg.get("remember_path"):
        cfg["last_video_dir"] = ""
    cfg["columns"] = clamp_int(cfg.get("columns"), 6, 4, 9)
    cfg["play_limit"] = clamp_int(cfg.get("play_limit"), 24, 12, 30)
    return cfg


def save_config(cfg: dict) -> dict:
    merged = dict(DEFAULT_CONFIG)
    merged.update({k: cfg.get(k, v) for k, v in DEFAULT_CONFIG.items()})
    merged["remember_path"] = bool(merged.get("remember_path"))
    merged["recursive"] = bool(merged.get("recursive"))
    merged["immersive"] = bool(merged.get("immersive"))
    merged["columns"] = clamp_int(merged.get("columns"), 6, 4, 9)
    merged["play_limit"] = clamp_int(merged.get("play_limit"), 24, 12, 30)
    if not merged["remember_path"]:
        merged["last_video_dir"] = ""
    else:
        merged["last_video_dir"] = normalize_path(merged.get("last_video_dir", ""))
    CONFIG_FILE.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    return merged


def get_current_video_dir() -> Path | None:
    with runtime_lock:
        p = runtime_video_dir
    if not p:
        return None
    return Path(p)


def set_current_video_dir(path: str):
    global runtime_video_dir
    with runtime_lock:
        runtime_video_dir = normalize_path(path)


def safe_rel_to_path(root: Path, rel: str) -> Path:
    rel = unquote(rel).replace("\\", "/")
    rel = posixpath.normpath(rel)
    if rel.startswith("../") or rel == ".." or os.path.isabs(rel):
        raise ValueError("Invalid path")
    root_resolved = root.resolve()
    full = (root_resolved / rel).resolve()
    try:
        full.relative_to(root_resolved)
    except ValueError:
        raise ValueError("Path outside video directory")
    return full


def scan_videos(video_dir: str, recursive: bool) -> tuple[list[dict], str | None]:
    root = Path(normalize_path(video_dir))
    if not str(root).strip():
        return [], "路径为空，请先输入或选择一个视频文件夹。"
    if not root.exists():
        return [], f"路径不存在：{root}"
    if not root.is_dir():
        return [], f"这不是文件夹路径：{root}"

    pattern = "**/*" if recursive else "*"
    files: list[Path] = []
    try:
        for p in root.glob(pattern):
            try:
                if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS:
                    files.append(p)
            except OSError:
                continue
    except Exception as exc:
        return [], f"扫描失败：{exc}"

    try:
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    except Exception:
        files.sort(key=lambda p: str(p).lower())

    videos = []
    root_resolved = root.resolve()
    for i, p in enumerate(files):
        try:
            st = p.stat()
            rel = p.resolve().relative_to(root_resolved).as_posix()
            videos.append({
                "id": i,
                "name": p.name,
                "rel": rel,
                "url": "/media?path=" + quote(rel, safe=""),
                "size_mb": round(st.st_size / 1024 / 1024, 2),
                "mtime": int(st.st_mtime),
                "mtime_text": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime)),
            })
        except Exception:
            continue
    return videos, None


def choose_folder_dialog() -> str:
    if os.name == "nt":
        script = r"""
Add-Type -AssemblyName System.Windows.Forms
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = "选择视频文件夹"
$dialog.ShowNewFolderButton = $false
$result = $dialog.ShowDialog()
if ($result -eq [System.Windows.Forms.DialogResult]::OK) {
  Write-Output $dialog.SelectedPath
}
"""
        try:
            completed = subprocess.run(
                ["powershell", "-NoProfile", "-STA", "-Command", script],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            selected = completed.stdout.strip()
            if selected:
                return selected
        except Exception:
            pass
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.askdirectory(title="选择视频文件夹")
        root.destroy()
        return selected or ""
    except Exception:
        return ""


class AppHandler(BaseHTTPRequestHandler):
    server_version = "LocalVideoWallV2/2.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def send_json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def serve_static(self, rel_path: str):
        if rel_path in ("", "/"):
            rel_path = "index.html"
        rel_path = rel_path.lstrip("/")
        full = (STATIC_DIR / rel_path).resolve()
        try:
            full.relative_to(STATIC_DIR.resolve())
        except ValueError:
            self.send_error(403)
            return
        if not full.exists() or not full.is_file():
            self.send_error(404)
            return
        mime, _ = mimetypes.guess_type(str(full))
        if not mime:
            mime = "application/octet-stream"
        data = full.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def serve_media(self, rel: str):
        root = get_current_video_dir()
        if root is None:
            self.send_error(404, "No video directory selected")
            return
        try:
            file_path = safe_rel_to_path(root, rel)
        except ValueError:
            self.send_error(403)
            return
        if not file_path.exists() or not file_path.is_file():
            self.send_error(404)
            return
        file_size = file_path.stat().st_size
        content_type = mimetypes.guess_type(str(file_path))[0] or "video/mp4"
        range_header = self.headers.get("Range")
        if range_header:
            m = re.match(r"bytes=(\d*)-(\d*)", range_header)
            if not m:
                self.send_error(416)
                return
            start_s, end_s = m.groups()
            if start_s == "" and end_s == "":
                self.send_error(416)
                return
            if start_s == "":
                length = int(end_s)
                start = max(file_size - length, 0)
                end = file_size - 1
            else:
                start = int(start_s)
                end = int(end_s) if end_s else file_size - 1
            if start >= file_size:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{file_size}")
                self.end_headers()
                return
            end = min(end, file_size - 1)
            chunk_size = end - start + 1
            self.send_response(206)
            self.send_header("Content-Type", content_type)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
            self.send_header("Content-Length", str(chunk_size))
            self.send_header("Cache-Control", "public, max-age=3600")
            self.end_headers()
            with open(file_path, "rb") as f:
                f.seek(start)
                remaining = chunk_size
                while remaining > 0:
                    chunk = f.read(min(1024 * 1024, remaining))
                    if not chunk:
                        break
                    try:
                        self.wfile.write(chunk)
                    except BrokenPipeError:
                        break
                    remaining -= len(chunk)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(file_size))
        self.send_header("Cache-Control", "public, max-age=3600")
        self.end_headers()
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except BrokenPipeError:
                    break

    def api_open_in_explorer(self, rel: str):
        root = get_current_video_dir()
        if root is None:
            self.send_json({"ok": False, "error": "请先选择并扫描视频文件夹。"}, 400)
            return
        try:
            file_path = safe_rel_to_path(root, rel)
        except ValueError:
            self.send_json({"ok": False, "error": "Invalid path"}, 403)
            return
        if not file_path.exists():
            self.send_json({"ok": False, "error": "File not found"}, 404)
            return
        if os.name == "nt":
            subprocess.Popen(["explorer", "/select,", str(file_path)])
            self.send_json({"ok": True})
        else:
            subprocess.Popen(["xdg-open", str(file_path.parent)])
            self.send_json({"ok": True})

    def do_GET(self):
        path, _, query = self.path.partition("?")
        qs = parse_qs(query)
        if path == "/api/config":
            cfg = load_config()
            if cfg.get("remember_path") and cfg.get("last_video_dir"):
                set_current_video_dir(cfg.get("last_video_dir"))
            self.send_json({"ok": True, "config": cfg})
            return
        if path == "/api/choose-folder":
            selected = choose_folder_dialog()
            self.send_json({"ok": True, "path": selected})
            return
        if path == "/api/open":
            rel = qs.get("path", [""])[0]
            self.api_open_in_explorer(rel)
            return
        if path == "/media":
            rel = qs.get("path", [""])[0]
            self.serve_media(rel)
            return
        if path == "/health":
            cfg = load_config()
            self.send_json({"ok": True, "config": cfg, "runtime_video_dir": str(get_current_video_dir() or "")})
            return
        if path == "/":
            self.serve_static("index.html")
        elif path.startswith("/static/"):
            self.serve_static(path[len("/static/"):])
        else:
            self.send_error(404)

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        payload = self.read_json_body()
        if path == "/api/scan":
            video_dir = normalize_path(payload.get("video_dir", ""))
            recursive = bool(payload.get("recursive", False))
            remember_path = bool(payload.get("remember_path", False))
            columns = clamp_int(payload.get("columns"), 6, 4, 9)
            play_limit = clamp_int(payload.get("play_limit"), 24, 12, 30)
            sort_mode = payload.get("sort_mode", "mtime_desc")
            immersive = bool(payload.get("immersive", False))
            videos, error = scan_videos(video_dir, recursive)
            if error:
                self.send_json({"ok": False, "error": error, "videos": []}, 400)
                return
            set_current_video_dir(video_dir)
            cfg = save_config({
                "remember_path": remember_path,
                "last_video_dir": video_dir if remember_path else "",
                "recursive": recursive,
                "columns": columns,
                "play_limit": play_limit,
                "sort_mode": sort_mode,
                "immersive": immersive,
            })
            self.send_json({
                "ok": True,
                "video_dir": video_dir,
                "count": len(videos),
                "recursive": recursive,
                "videos": videos,
                "config": cfg,
            })
            return
        if path == "/api/settings":
            cfg = load_config()
            cfg.update({
                "remember_path": bool(payload.get("remember_path", cfg.get("remember_path", False))),
                "recursive": bool(payload.get("recursive", cfg.get("recursive", False))),
                "columns": clamp_int(payload.get("columns", cfg.get("columns", 6)), 6, 4, 9),
                "play_limit": clamp_int(payload.get("play_limit", cfg.get("play_limit", 24)), 24, 12, 30),
                "sort_mode": payload.get("sort_mode", cfg.get("sort_mode", "mtime_desc")),
                "immersive": bool(payload.get("immersive", cfg.get("immersive", False))),
            })
            current = str(get_current_video_dir() or "")
            if cfg.get("remember_path"):
                cfg["last_video_dir"] = normalize_path(payload.get("last_video_dir", current))
            else:
                cfg["last_video_dir"] = ""
            cfg = save_config(cfg)
            self.send_json({"ok": True, "config": cfg})
            return
        self.send_error(404)


def main():
    cfg = load_config()
    if cfg.get("remember_path") and cfg.get("last_video_dir"):
        set_current_video_dir(cfg["last_video_dir"])
    print("=" * 72)
    print("Local Civitai-style Video Wall v2")
    print("=" * 72)
    print("Path input is empty by default unless 'remember path' was enabled.")
    print(f"Remembered folder: {cfg.get('last_video_dir') or '(empty)'}")
    print(f"Open in browser: http://{HOST}:{PORT}")
    print("=" * 72)
    server = ThreadingHTTPServer((HOST, PORT), AppHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")


if __name__ == "__main__":
    main()
