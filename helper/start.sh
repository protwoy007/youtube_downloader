#!/usr/bin/env bash
# YT Local Downloader helper for Linux (and macOS). Run: bash helper/start.sh
cd "$(dirname "$(readlink -f "$0")")" || exit 1
HERE="$(pwd)"
PY="$HERE/.venv/bin/python"

if (command -v ss >/dev/null && ss -ltn 2>/dev/null | grep -q ":9477 "); then
  echo "Helper is already running."; exit 0
fi

echo "[1/5] Checking Python..."
if ! command -v python3 >/dev/null; then
  echo "    python3 not found. Install it, e.g.: sudo apt install python3 python3-venv python3-pip"
  exit 1
fi
echo "    OK"

echo "[2/5] Checking virtual environment..."
if [ ! -x "$PY" ]; then
  echo "    Creating..."
  python3 -m venv .venv || { echo "    Failed. Try: sudo apt install python3-venv"; exit 1; }
fi
echo "    OK"

echo "[3/5] Installing / updating yt-dlp..."
"$PY" -m pip install -q -U "yt-dlp[default,curl-cffi]" || { echo "    pip failed"; exit 1; }
echo "    OK"

echo "[4/5] Checking ffmpeg and deno (server.py downloads them if missing)..."
command -v ffmpeg >/dev/null && echo "    ffmpeg: system" || echo "    ffmpeg: will be downloaded to helper/bin"
command -v deno   >/dev/null && echo "    deno: system"   || echo "    deno: will be downloaded to helper/bin"

echo "[5/5] Registering ytdl:// link (lets the Download button start this helper)..."
if command -v xdg-mime >/dev/null; then
  mkdir -p "$HOME/.local/share/applications"
  cat > "$HOME/.local/share/applications/ytdl-helper.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=YT Local Downloader Helper
Exec=bash "$HERE/start.sh"
Terminal=true
NoDisplay=true
MimeType=x-scheme-handler/ytdl;
DESK
  xdg-mime default ytdl-helper.desktop x-scheme-handler/ytdl 2>/dev/null
  update-desktop-database "$HOME/.local/share/applications" 2>/dev/null
  echo "    OK"
else
  echo "    xdg-mime not found; start the helper manually with: bash helper/start.sh"
fi

echo
echo "Starting helper. Keep this window open."
exec "$PY" server.py
