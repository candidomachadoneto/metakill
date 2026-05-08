#!/bin/bash
# MetaKill — macOS installer
set -e

echo "=== MetaKill installer (macOS) ==="

# Homebrew check
if ! command -v brew &>/dev/null; then
    echo "ERROR: Homebrew not found."
    echo "Install from: https://brew.sh"
    exit 1
fi

echo "[1/4] Installing exiftool..."
brew install exiftool

echo "[2/4] Installing ffmpeg..."
brew install ffmpeg

echo "[3/4] Installing Python/tkinter (if missing)..."
brew install python-tk 2>/dev/null || true

echo "[4/4] Installing Pillow (PNG deep cleaning)..."
pip3 install --upgrade Pillow

echo ""
echo "✓ Done! Run:"
echo "  python3 $(dirname "$0")/metakill.py"
