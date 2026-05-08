#!/usr/bin/env python3
"""Generate MetaKill icon.ico using Pillow."""
from PIL import Image, ImageDraw, ImageFont

BG     = (15, 15, 26, 255)       # #0f0f1a
RED    = (233, 69, 96, 255)       # #e94560
WHITE  = (234, 240, 255, 255)     # #eaf0ff
TRANSP = (0, 0, 0, 0)

def make_frame(size: int) -> Image.Image:
    img = Image.new('RGBA', (size, size), TRANSP)
    draw = ImageDraw.Draw(img)
    m = max(1, size // 16)

    # Background circle
    draw.ellipse([m, m, size - m - 1, size - m - 1], fill=BG)

    # Red ring
    ring_w = max(1, size // 14)
    draw.ellipse([m + ring_w, m + ring_w,
                  size - m - ring_w - 1, size - m - ring_w - 1],
                 outline=RED, width=ring_w)

    # "MK" text
    font_sz = max(5, size * 28 // 100)
    font = None
    for fname in ('arialbd.ttf', 'Arial Bold.ttf', 'DejaVuSans-Bold.ttf',
                  'LiberationSans-Bold.ttf', 'arial.ttf'):
        try:
            font = ImageFont.truetype(fname, font_sz)
            break
        except OSError:
            pass
    if font is None:
        font = ImageFont.load_default()

    text = 'MK'
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        ((size - tw) // 2 - bbox[0], (size - th) // 2 - bbox[1]),
        text, fill=RED, font=font,
    )
    return img


def main():
    sizes = [16, 24, 32, 48, 64, 128, 256]
    frames = [make_frame(s) for s in sizes]
    frames[0].save(
        'icon.ico',
        format='ICO',
        sizes=[(s, s) for s in sizes],
        append_images=frames[1:],
    )
    print('Generated: icon.ico')


if __name__ == '__main__':
    main()
