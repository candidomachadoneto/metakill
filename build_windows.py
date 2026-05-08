#!/usr/bin/env python3
"""
MetaKill — Windows build script.

Run once on a Windows machine with Python 3.10+ installed:
    python build_windows.py

What this does:
  1. pip install pyinstaller pillow
  2. Generates icon.ico
  3. Downloads exiftool.exe (~6MB) from exiftool.org
  4. Downloads ffmpeg.exe (~100MB) from GitHub
  5. Bundles everything into dist\\MetaKill\\MetaKill.exe via PyInstaller
  6. If Inno Setup 6 is installed, creates dist\\MetaKill_Setup.exe (installer)
     Otherwise, creates dist\\MetaKill_Windows.zip (portable)

Requirements:
  - Windows 10/11
  - Python 3.10+ with pip  (python.org — check "Add to PATH")
  - ~2GB free disk, internet connection
  - Optional: Inno Setup 6 (jrsoftware.org/isinfo.php) for a proper installer
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from urllib import request
from urllib.error import URLError

BUILD_DIR  = Path("_build")
BIN_DIR    = BUILD_DIR / "bin"
DIST_DIR   = Path("dist")

EXIFTOOL_VERSION = "13.55"
EXIFTOOL_URL = f"https://exiftool.org/exiftool-{EXIFTOOL_VERSION}_64.zip"

FFMPEG_VERSION = "7.1"
FFMPEG_URL = (
    f"https://github.com/GyanD/codexffmpeg/releases/download/{FFMPEG_VERSION}/"
    f"ffmpeg-{FFMPEG_VERSION}-essentials_build.zip"
)

ISCC_PATHS = [
    r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    r"C:\Program Files\Inno Setup 6\ISCC.exe",
]

BANNER = """
╔══════════════════════════════════════╗
║   MetaKill — Windows Build Script   ║
╚══════════════════════════════════════╝
"""


# ─── Helpers ──────────────────────────────────────────────────────────────────

def step(n: int, total: int, label: str) -> None:
    print(f"\n[{n}/{total}] {label}")


def ok(msg: str = "Done") -> None:
    print(f"  ✓ {msg}")


def fail(msg: str) -> None:
    print(f"\n  ✗ ERROR: {msg}")
    input("\nPress Enter to exit...")
    sys.exit(1)


def run(cmd: list[str], **kwargs) -> None:
    r = subprocess.run(cmd, **kwargs)
    if r.returncode != 0:
        fail(f"Command failed: {' '.join(str(c) for c in cmd)}")


def download_file(url: str, dest: Path, label: str) -> None:
    if dest.exists():
        ok(f"{label} already cached")
        return

    print(f"  Downloading {label}...")
    try:
        def _progress(count: int, block: int, total: int) -> None:
            if total > 0:
                pct = min(100, count * block * 100 // total)
                mb  = count * block / 1_048_576
                print(f"\r  {pct:3d}%  {mb:.1f} MB", end='', flush=True)

        request.urlretrieve(url, dest, reporthook=_progress)
        print()
        ok(f"{label} downloaded ({dest.stat().st_size // 1_048_576} MB)")
    except URLError as e:
        fail(f"Download failed ({url}): {e}")


def extract_file(zip_path: Path, match_suffix: str, dest: Path) -> None:
    """Extract the first file matching match_suffix from zip to dest."""
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            if name.endswith(match_suffix):
                dest.write_bytes(z.read(name))
                ok(f"Extracted {dest.name} ({dest.stat().st_size // 1_048_576} MB)")
                return
    fail(f"Could not find '{match_suffix}' inside {zip_path.name}")


# ─── Build steps ──────────────────────────────────────────────────────────────

def install_python_deps() -> None:
    run([sys.executable, "-m", "pip", "install",
         "pyinstaller>=6.0", "pillow>=10.0",
         "--quiet", "--upgrade"])
    ok("pyinstaller + pillow")


def generate_icon() -> None:
    if not Path("create_icon.py").exists():
        print("  create_icon.py not found — skipping icon")
        return
    run([sys.executable, "create_icon.py"])


def download_exiftool() -> None:
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    exe = BIN_DIR / "exiftool.exe"
    if exe.exists():
        ok(f"exiftool cached ({exe.stat().st_size // 1024} KB)")
        return

    zip_path = BUILD_DIR / "exiftool.zip"
    download_file(EXIFTOOL_URL, zip_path, "exiftool")

    # The zip contains 'exiftool(-k).exe' — rename to exiftool.exe
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            if name.endswith('.exe') and 'exiftool' in name.lower():
                exe.write_bytes(z.read(name))
                ok(f"exiftool.exe ready ({exe.stat().st_size // 1024} KB)")
                break
        else:
            fail("exiftool.exe not found inside downloaded zip")

    zip_path.unlink(missing_ok=True)


def download_ffmpeg() -> None:
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    exe = BIN_DIR / "ffmpeg.exe"
    if exe.exists():
        ok(f"ffmpeg cached ({exe.stat().st_size // 1_048_576} MB)")
        return

    zip_path = BUILD_DIR / "ffmpeg.zip"
    download_file(FFMPEG_URL, zip_path, f"ffmpeg {FFMPEG_VERSION}")
    # GyanD essentials build path: ffmpeg-7.1-essentials_build/bin/ffmpeg.exe
    extract_file(zip_path, "bin/ffmpeg.exe", exe)
    zip_path.unlink(missing_ok=True)


def build_exe() -> None:
    exiftool_exe = BIN_DIR / "exiftool.exe"
    ffmpeg_exe   = BIN_DIR / "ffmpeg.exe"

    if not exiftool_exe.exists():
        fail("exiftool.exe not found in _build/bin/")
    if not ffmpeg_exe.exists():
        fail("ffmpeg.exe not found in _build/bin/")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onedir",
        "--windowed",
        "--name", "MetaKill",
        f"--add-binary={exiftool_exe};.",
        f"--add-binary={ffmpeg_exe};.",
        "--clean",
        "--noconfirm",
        "metakill.py",
    ]

    if Path("icon.ico").exists():
        cmd.insert(-1, "--icon=icon.ico")

    print("  Running PyInstaller (2–4 minutes)…")
    run(cmd)
    ok(f"dist\\MetaKill\\MetaKill.exe")


def create_installer() -> bool:
    """Try Inno Setup. Returns True if installer was created."""
    iscc = next((p for p in ISCC_PATHS if Path(p).exists()), None)
    if not iscc:
        return False
    if not Path("metakill.iss").exists():
        return False

    print("  Running Inno Setup…")
    r = subprocess.run([iscc, "metakill.iss"])
    if r.returncode == 0:
        ok("dist\\MetaKill_Setup.exe")
        return True
    return False


def create_zip_fallback() -> None:
    out = DIST_DIR / "MetaKill_Windows.zip"
    print(f"  Creating {out.name}…")
    shutil.make_archive(str(DIST_DIR / "MetaKill_Windows"), "zip",
                        str(DIST_DIR), "MetaKill")
    ok(f"{out.name} ({out.stat().st_size // 1_048_576} MB)")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    print(BANNER)

    if sys.platform != "win32":
        print("WARNING: This script is designed to run on Windows.")
        print("         On macOS/Linux, use run.sh instead.")
        print()

    if not Path("metakill.py").exists():
        fail("metakill.py not found. Run this script from the metakill/ folder.")

    TOTAL = 6

    step(1, TOTAL, "Installing Python dependencies")
    install_python_deps()

    step(2, TOTAL, "Generating icon")
    generate_icon()

    step(3, TOTAL, "Downloading exiftool")
    download_exiftool()

    step(4, TOTAL, "Downloading ffmpeg")
    download_ffmpeg()

    step(5, TOTAL, "Building MetaKill.exe with PyInstaller")
    build_exe()

    step(6, TOTAL, "Creating installer")
    if not create_installer():
        print("  Inno Setup not found — creating zip instead.")
        print("  For a proper installer, install Inno Setup 6:")
        print("  https://jrsoftware.org/isinfo.php")
        print("  Then run: python build_windows.py  (again, after install)")
        create_zip_fallback()

    print()
    print("╔══════════════════════════════════════╗")
    print("║          BUILD COMPLETE!             ║")
    print("╚══════════════════════════════════════╝")
    print()

    out_installer = DIST_DIR / "MetaKill_Setup.exe"
    out_zip       = DIST_DIR / "MetaKill_Windows.zip"
    out_exe       = DIST_DIR / "MetaKill" / "MetaKill.exe"

    if out_installer.exists():
        print(f"  Installer: {out_installer}")
        print("  → Copy to Windows machine and double-click to install.")
    elif out_zip.exists():
        print(f"  Zip:       {out_zip}")
        print("  → Extract and run MetaKill\\MetaKill.exe")
    print(f"  Raw exe:   {out_exe}")
    print()
    input("Press Enter to exit...")


if __name__ == "__main__":
    main()
