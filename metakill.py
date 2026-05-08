#!/usr/bin/env python3
"""
MetaKill v1.0 — Deep Metadata Anonymizer
Strips ALL identifying metadata from images and videos.

What is removed:
  Images: EXIF (GPS, device model, serial, lens, timestamps), IPTC, XMP,
          ICC profiles, PNG hidden chunks (tEXt/iTXt/zTXt), file timestamps.
  Videos: Container atoms (QuickTime/MP4/MKV metadata), chapter info,
          embedded thumbnails, encoder strings, creation timestamps.
          Deep mode also re-encodes the bitstream, wiping stream-level
          SEI NAL units (H.264/H.265 device/encoder IDs baked in).

Limitations (cannot be removed by this tool):
  - Steganographic watermarks (Getty, platform fingerprinting)
  - PRNU camera sensor fingerprints (pixel-level noise patterns)
  - Visual watermarks (TikTok/Instagram logos embedded in pixels)

Requires: exiftool, ffmpeg
Optional: Pillow (pip install Pillow) for PNG pixel-level chunk removal
"""

from __future__ import annotations

import os
import sys
import shutil
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog
from pathlib import Path

VERSION = "1.0"

IMAGE_EXTS = frozenset({
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif',
    '.webp', '.heic', '.heif', '.cr2', '.nef', '.arw', '.dng',
    '.raw', '.avif', '.psd',
})

VIDEO_EXTS = frozenset({
    '.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm',
    '.m4v', '.3gp', '.ts', '.mts', '.m2ts', '.ogv', '.mpg',
    '.mpeg', '.mxf', '.vob', '.divx',
})

EPOCH = 0  # 1970-01-01 00:00:00 UTC

C = {
    'bg':       '#0f0f1a',
    'surface':  '#1a1a2e',
    'surface2': '#16213e',
    'accent':   '#e94560',
    'ok':       '#00b894',
    'warn':     '#fdcb6e',
    'text':     '#eaf0ff',
    'muted':    '#7f8c9a',
    'border':   '#2d2d4e',
}


# ─── Tool detection ───────────────────────────────────────────────────────────

def which(name: str) -> str | None:
    """Locate a binary — checks PyInstaller bundle, then exe dir, then PATH."""
    exe_name = f'{name}.exe' if sys.platform == 'win32' else name

    # PyInstaller one-file: extracted to sys._MEIPASS
    # PyInstaller one-dir:  lives next to sys.executable
    search_dirs: list[Path] = []
    if hasattr(sys, '_MEIPASS'):
        search_dirs.append(Path(sys._MEIPASS))
    search_dirs.append(Path(sys.executable).parent)

    for base in search_dirs:
        for fname in (exe_name, name):
            candidate = base / fname
            if candidate.is_file():
                return str(candidate)

    # System PATH
    p = shutil.which(name)
    if p:
        return p

    # Common macOS Homebrew paths
    if sys.platform == 'darwin':
        for prefix in ('/opt/homebrew/bin', '/usr/local/bin', '/usr/bin'):
            full = Path(prefix) / name
            if full.is_file():
                return str(full)

    return None


# ─── Core strip functions ─────────────────────────────────────────────────────

def strip_image(src: Path, dst: Path, reset_ts: bool, log) -> bool:
    """Strip all metadata from an image. Returns True on success."""
    shutil.copy2(src, dst)

    exiftool = which('exiftool')
    if not exiftool:
        log('  ✗ exiftool not found — install it first', 'err')
        dst.unlink(missing_ok=True)
        return False

    r = subprocess.run(
        [exiftool, '-all=', '-overwrite_original', str(dst)],
        capture_output=True, text=True, timeout=60,
    )
    if r.returncode != 0:
        log(f'  ✗ exiftool: {r.stderr.strip()[:120]}', 'err')
        return False

    # PNG secondary pass: pixel-copy through Pillow kills tEXt/iTXt/zTXt chunks
    # that exiftool may leave behind in some PNG variants
    if dst.suffix.lower() == '.png':
        _png_deep_clean(dst, log)

    if reset_ts:
        os.utime(dst, (EPOCH, EPOCH))

    return True


def _png_deep_clean(path: Path, log) -> None:
    try:
        from PIL import Image  # type: ignore
        img = Image.open(path)
        clean = Image.new(img.mode, img.size)
        clean.putdata(list(img.getdata()))
        clean.save(path, 'PNG', optimize=False)
    except ImportError:
        pass  # Pillow not installed — exiftool pass was sufficient
    except Exception as e:
        log(f'  ⚠ PNG deep pass skipped: {e}', 'warn')


def strip_video(src: Path, dst: Path, deep: bool, reset_ts: bool, log) -> bool:
    """Strip all metadata from a video. Returns True on success."""
    ffmpeg = which('ffmpeg')
    exiftool = which('exiftool')

    if not ffmpeg:
        log('  ✗ ffmpeg not found — install it first', 'err')
        return False

    if deep:
        # Full re-encode: wipes stream-level SEI NAL units, encoder identity
        # strings, device fingerprints baked into H.264/H.265 bitstream.
        # -pix_fmt yuv420p removes unusual pixel format hints.
        # -ac 2 normalizes to stereo (removes multi-channel spatial metadata).
        cmd = [
            ffmpeg, '-y', '-i', str(src),
            '-map_metadata', '-1',      # Kill ALL container metadata
            '-map_chapters', '-1',      # Kill chapter markers
            '-c:v', 'libx264',          # Re-encode video stream
            '-preset', 'slow',          # Slow = better compression = different bitstream pattern
            '-crf', '18',               # Near-lossless quality
            '-pix_fmt', 'yuv420p',      # Standardize pixel format
            '-c:a', 'aac',              # Re-encode audio stream
            '-b:a', '192k',
            '-ac', '2',                 # Force stereo
            '-movflags', '+faststart',  # Reorder atoms for web (also normalizes structure)
            str(dst),
        ]
        label = 'deep re-encode'
    else:
        # Stream copy: strips only container-level metadata atoms. Faster, lossless.
        # Does NOT remove SEI metadata embedded inside the bitstream.
        cmd = [
            ffmpeg, '-y', '-i', str(src),
            '-map_metadata', '-1',
            '-map_chapters', '-1',
            '-c', 'copy',
            str(dst),
        ]
        label = 'fast strip'

    log(f'  ⟳ ffmpeg ({label})…', 'info')
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)

    if r.returncode != 0:
        errs = [l for l in r.stderr.splitlines()
                if any(w in l for w in ('Error', 'error', 'Invalid', 'failed', 'Conversion'))]
        msg = errs[-1].strip()[:120] if errs else 'unknown error'
        log(f'  ✗ ffmpeg: {msg}', 'err')
        return False

    # Post-pass: exiftool on output to catch any container-level residuals
    if exiftool:
        subprocess.run(
            [exiftool, '-all=', '-overwrite_original', str(dst)],
            capture_output=True, timeout=60,
        )

    if reset_ts:
        os.utime(dst, (EPOCH, EPOCH))

    return True


def resolve_output(src: Path, dst_dir: Path, rename: bool, idx: int) -> Path:
    if rename:
        return dst_dir / f'file_{idx:04d}{src.suffix.lower()}'
    return dst_dir / src.name


# ─── GUI ──────────────────────────────────────────────────────────────────────

class App(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title(f'MetaKill v{VERSION}')
        self.geometry('760x600')
        self.minsize(600, 500)
        self.configure(bg=C['bg'])

        self.files: list[Path] = []
        self._running = False

        self.v_deep    = tk.BooleanVar(value=True)
        self.v_ts      = tk.BooleanVar(value=True)
        self.v_rename  = tk.BooleanVar(value=False)
        self.v_outmode = tk.StringVar(value='sub')
        self.v_outdir  = tk.StringVar(value='')

        self._build()
        threading.Thread(target=self._check_tools, daemon=True).start()

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build(self):
        # Header
        hdr = tk.Frame(self, bg=C['surface'], height=52)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)
        tk.Label(hdr, text='MetaKill', font=('Courier New', 18, 'bold'),
                 fg=C['accent'], bg=C['surface']).pack(side='left', padx=14)
        tk.Label(hdr, text='deep metadata anonymizer', font=('Courier New', 9),
                 fg=C['muted'], bg=C['surface']).pack(side='left', pady=16)
        self._tool_lbl = tk.Label(hdr, text='checking tools…',
                                   font=('Courier New', 8), fg=C['muted'], bg=C['surface'])
        self._tool_lbl.pack(side='right', padx=14)

        # Drop zone
        dz_frame = tk.Frame(self, bg=C['bg'], padx=14, pady=8)
        dz_frame.pack(fill='x')
        self._dz = tk.Label(
            dz_frame,
            text='[ click to add files ]\n'
                 'images: jpg  png  webp  heic  gif  tiff  raw  dng  cr2  nef  arw  avif  psd\n'
                 'videos: mp4  mov  mkv  avi  wmv  webm  m4v  3gp  flv  ts  mts  ogv  mxf',
            font=('Courier New', 10), fg=C['muted'], bg=C['surface2'],
            relief='flat', pady=22, cursor='hand2',
        )
        self._dz.pack(fill='x')
        self._dz.bind('<Button-1>', lambda _: self._add_files())

        self._files_lbl = tk.Label(
            dz_frame, text='No files selected.',
            font=('Courier New', 8), fg=C['muted'], bg=C['bg'], anchor='w',
        )
        self._files_lbl.pack(fill='x', pady=(3, 0))

        # Options panel
        opt = tk.Frame(self, bg=C['surface2'], padx=14, pady=10)
        opt.pack(fill='x')

        tk.Label(opt, text='OPTIONS', font=('Courier New', 7, 'bold'),
                 fg=C['muted'], bg=C['surface2']).grid(row=0, column=0, columnspan=5,
                 sticky='w', pady=(0, 6))

        ck = dict(font=('Courier New', 10), fg=C['text'], bg=C['surface2'],
                  activeforeground=C['text'], activebackground=C['surface2'],
                  selectcolor=C['bg'])
        rk = dict(font=('Courier New', 10), fg=C['text'], bg=C['surface2'],
                  activeforeground=C['text'], activebackground=C['surface2'],
                  selectcolor=C['bg'], variable=self.v_outmode)

        tk.Checkbutton(
            opt,
            text='Deep mode — re-encode video (strips SEI NAL units, encoder ID, bitstream fingerprints)',
            variable=self.v_deep, **ck,
        ).grid(row=1, column=0, columnspan=5, sticky='w')

        tk.Checkbutton(
            opt,
            text='Reset file timestamps → 1970-01-01 00:00:00 UTC (removes access/modify/create dates)',
            variable=self.v_ts, **ck,
        ).grid(row=2, column=0, columnspan=5, sticky='w')

        tk.Checkbutton(
            opt,
            text='Rename output files as file_0001.ext (severs original filename from output)',
            variable=self.v_rename, **ck,
        ).grid(row=3, column=0, columnspan=5, sticky='w')

        tk.Label(opt, text='Output:', font=('Courier New', 10),
                 fg=C['text'], bg=C['surface2']).grid(row=4, column=0, sticky='w', pady=(8, 0))
        tk.Radiobutton(opt, text='cleaned/ subfolder', value='sub', **rk
                       ).grid(row=4, column=1, sticky='w', padx=(6, 0), pady=(8, 0))
        tk.Radiobutton(opt, text='custom folder', value='custom', **rk
                       ).grid(row=4, column=2, sticky='w', padx=(6, 0), pady=(8, 0))
        tk.Button(opt, text='Browse…', font=('Courier New', 8), fg=C['text'],
                  bg=C['border'], relief='flat', padx=6,
                  command=self._browse_out).grid(row=4, column=3, padx=(8, 0), pady=(8, 0))

        tk.Label(opt, textvariable=self.v_outdir, font=('Courier New', 7),
                 fg=C['muted'], bg=C['surface2']).grid(row=5, column=1, columnspan=4, sticky='w')

        # Progress bar
        pb_frame = tk.Frame(self, bg=C['bg'], padx=14, pady=4)
        pb_frame.pack(fill='x')

        style = ttk.Style()
        style.theme_use('default')
        style.configure('TProgressbar', troughcolor=C['surface'],
                        background=C['accent'], thickness=5)
        self._bar = ttk.Progressbar(pb_frame, mode='determinate')
        self._bar.pack(fill='x')

        self._bar_lbl = tk.Label(pb_frame, text='', font=('Courier New', 7),
                                  fg=C['muted'], bg=C['bg'])
        self._bar_lbl.pack(anchor='w')

        # Log area
        log_frame = tk.Frame(self, bg=C['bg'], padx=14, pady=0)
        log_frame.pack(fill='both', expand=True)

        self._log = tk.Text(
            log_frame, font=('Courier New', 9), fg=C['text'], bg=C['surface'],
            relief='flat', padx=8, pady=6, state='disabled', wrap='word',
        )
        sb = tk.Scrollbar(log_frame, command=self._log.yview, bg=C['surface'])
        self._log.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        self._log.pack(fill='both', expand=True)

        self._log.tag_configure('ok',   foreground=C['ok'])
        self._log.tag_configure('err',  foreground=C['accent'])
        self._log.tag_configure('warn', foreground=C['warn'])
        self._log.tag_configure('info', foreground=C['muted'])

        # Bottom buttons
        btn_frame = tk.Frame(self, bg=C['bg'], padx=14, pady=10)
        btn_frame.pack(fill='x')

        tk.Button(
            btn_frame, text='Clear', font=('Courier New', 10),
            fg=C['muted'], bg=C['surface'], relief='flat', padx=10, pady=5,
            command=self._clear,
        ).pack(side='left')

        self._run_btn = tk.Button(
            btn_frame, text='STRIP CLEAN',
            font=('Courier New', 12, 'bold'), fg='white', bg=C['accent'],
            relief='flat', padx=20, pady=5, command=self._start,
        )
        self._run_btn.pack(side='right')

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _check_tools(self):
        missing = [t for t in ('exiftool', 'ffmpeg') if not which(t)]
        if missing:
            msg = f'MISSING: {", ".join(missing)}'
            col = C['accent']
        else:
            msg = '✓ exiftool + ffmpeg ready'
            col = C['ok']
        self.after(0, lambda: self._tool_lbl.configure(text=msg, fg=col))

    def _add_files(self):
        all_exts = ' '.join(f'*{e}' for e in sorted(IMAGE_EXTS | VIDEO_EXTS))
        paths = filedialog.askopenfilenames(
            title='Select files to anonymize',
            filetypes=[
                ('Supported files', all_exts),
                ('All files', '*.*'),
            ],
        )
        for p in paths:
            path = Path(p)
            if path not in self.files:
                self.files.append(path)
        self._refresh_files_lbl()

    def _clear(self):
        self.files.clear()
        self._refresh_files_lbl()
        self._bar['value'] = 0
        self._bar_lbl.configure(text='')

    def _refresh_files_lbl(self):
        n = len(self.files)
        if n == 0:
            self._files_lbl.configure(text='No files selected.')
            return
        imgs = sum(1 for f in self.files if f.suffix.lower() in IMAGE_EXTS)
        vids = sum(1 for f in self.files if f.suffix.lower() in VIDEO_EXTS)
        parts: list[str] = []
        if imgs:
            parts.append(f'{imgs} image{"s" if imgs > 1 else ""}')
        if vids:
            parts.append(f'{vids} video{"s" if vids > 1 else ""}')
        self._files_lbl.configure(
            text=f'{n} file{"s" if n > 1 else ""} queued — {", ".join(parts)}'
        )

    def _browse_out(self):
        d = filedialog.askdirectory(title='Select output folder')
        if d:
            self.v_outdir.set(d)
            self.v_outmode.set('custom')

    def _log_write(self, msg: str, tag: str = 'info'):
        def _do():
            self._log.configure(state='normal')
            self._log.insert('end', msg + '\n', tag)
            self._log.see('end')
            self._log.configure(state='disabled')
        self.after(0, _do)

    def _update_progress(self, n: int, total: int):
        def _do():
            self._bar['value'] = n / total * 100
            self._bar_lbl.configure(text=f'{n}/{total} files processed')
        self.after(0, _do)

    # ── Processing ────────────────────────────────────────────────────────────

    def _start(self):
        if self._running:
            return
        if not self.files:
            self._log_write('No files selected.', 'warn')
            return
        self._running = True
        self._run_btn.configure(state='disabled', text='Running…')
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        files  = list(self.files)
        deep   = self.v_deep.get()
        rts    = self.v_ts.get()
        rename = self.v_rename.get()
        total  = len(files)
        ok = fail = 0

        self._log_write('─' * 56, 'info')
        self._log_write(
            f'Processing {total} file(s) | '
            f'mode={"deep" if deep else "fast"} | '
            f'reset_timestamps={rts} | rename={rename}',
            'info',
        )

        for idx, src in enumerate(files, 1):
            ext = src.suffix.lower()
            is_img = ext in IMAGE_EXTS
            is_vid = ext in VIDEO_EXTS

            if self.v_outmode.get() == 'custom' and self.v_outdir.get():
                dst_dir = Path(self.v_outdir.get())
            else:
                dst_dir = src.parent / 'cleaned'

            dst_dir.mkdir(parents=True, exist_ok=True)
            dst = resolve_output(src, dst_dir, rename, idx)

            self._log_write(f'→ [{idx}/{total}] {src.name}', 'info')

            def log(msg: str, tag: str = 'info'):  # closure over self
                self._log_write(msg, tag)

            if is_img:
                success = strip_image(src, dst, rts, log)
            elif is_vid:
                success = strip_video(src, dst, deep, rts, log)
            else:
                log(f'  ⚠ unsupported extension: {ext}', 'warn')
                success = False

            if success:
                ok += 1
                self._log_write(f'  ✓ saved → {dst}', 'ok')
            else:
                fail += 1

            self._update_progress(idx, total)

        self._log_write('─' * 56, 'info')
        result_tag = 'ok' if fail == 0 else 'warn'
        self._log_write(
            f'Finished. {ok} cleaned successfully, {fail} failed.',
            result_tag,
        )

        self._running = False
        self.after(0, lambda: self._run_btn.configure(state='normal', text='STRIP CLEAN'))


# ─── Entry point ─────────────────────────────────────────────────────────────

if __name__ == '__main__':
    App().mainloop()
