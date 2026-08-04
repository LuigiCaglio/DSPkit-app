"""
Build the final DSPkit logo assets from the chosen "Wave -> Spectrum" concept
(see generate_dspkit_logo_concepts.py for the design survey).

Same source math drives every output so the badge favicon, the .ico, and the
inline Svelte component are all the same mark:

  - frontend/public/dspkit_logo_icon.svg   standalone vector badge
  - frontend/public/dspkit_favicon_*.png   16/32/64/128/256 px PNGs
  - dspkit.ico                              multi-res Windows icon (shortcut)
  - prints an SVG <path> "d" string for the transparent, no-badge in-app
    mark, to paste into frontend/src/lib/DspkitLogo.svelte
"""

from pathlib import Path

import numpy as np
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from PIL import Image

ACCENT = '#10b981'  # frontend/src/lib/theme.svelte.js -> daylight theme accent (default)
ROOT = Path(__file__).resolve().parents[2]  # DSPkit-app/
PUBLIC = ROOT / 'frontend' / 'public'
PUBLIC.mkdir(parents=True, exist_ok=True)


# ── shared geometry (100x100 icon space) ───────────────────────────────────
# Wavelength (span/cycles) must stay comfortably larger than the stroke
# width (in the same data units) or the loops merge into a solid blob --
# that's what happened on the first pass (5.5 cycles over 34 units with a
# 5.4pt stroke). Fewer, wider cycles + a thinner stroke + a taper on both
# ends (not just the trailing one) reads as a clean signal at 16px too.
WAVE_LW = 3.6  # pt


def wave_xy(x0=8, span=33, y0=54, amp=13, cycles=3, n=120):
    t = np.linspace(0, span, n)
    envelope = np.sin(np.pi * t / span) ** 0.7  # tapers to 0 at both ends
    y = y0 + amp * envelope * np.sin(2 * np.pi * cycles * t / span)
    return x0 + t, y


BAR_X = np.array([64, 71, 78, 85, 92])
BAR_H = np.array([15, 27, 20, 12, 7])
BAR_BASE = 34
BAR_W = 5.4

ARROW_X0, ARROW_X1, ARROW_Y = 47, 59, 54


def draw_mark(ax, fg, badge_bg=None, badge_pad=4, badge_round=20):
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.set_aspect('equal')
    ax.axis('off')

    if badge_bg:
        ax.add_patch(mpatches.FancyBboxPatch(
            (badge_pad, badge_pad), 100 - 2 * badge_pad, 100 - 2 * badge_pad,
            boxstyle=f'round,pad=0,rounding_size={badge_round}',
            linewidth=0, facecolor=badge_bg))

    wx, wy = wave_xy()
    ax.plot(wx, wy, color=fg, linewidth=WAVE_LW, solid_capstyle='round', solid_joinstyle='round')

    ax.annotate('', xy=(ARROW_X1, ARROW_Y), xytext=(ARROW_X0, ARROW_Y),
                arrowprops=dict(arrowstyle='-|>', color=fg, linewidth=3, alpha=0.95,
                                 mutation_scale=18))

    ax.bar(BAR_X, BAR_H, bottom=BAR_BASE, width=BAR_W, color=fg)


# ── 1. favicon badge PNGs (rendered once at high res, downsampled) ────────
def build_pngs():
    fig = plt.figure(figsize=(1, 1), dpi=512)
    ax = fig.add_axes([0, 0, 1, 1])
    fig.patch.set_alpha(0)
    draw_mark(ax, fg='white', badge_bg=ACCENT)
    master_path = PUBLIC / '_dspkit_master_512.png'
    fig.savefig(master_path, transparent=True)
    plt.close(fig)

    master = Image.open(master_path).convert('RGBA')
    sizes = [16, 32, 48, 64, 128, 256, 512]
    pngs = {}
    for s in sizes:
        img = master.resize((s, s), Image.LANCZOS)
        out = PUBLIC / f'dspkit_favicon_{s}x{s}.png'
        img.save(out)
        pngs[s] = img
        print(f'[OK] {out.name}')

    ico_path = ROOT / 'dspkit.ico'
    ico_sizes = [16, 32, 48, 64, 128, 256]
    pngs[ico_sizes[0]].save(
        ico_path, format='ICO',
        sizes=[(s, s) for s in ico_sizes],
        append_images=[pngs[s] for s in ico_sizes[1:]],
    )
    print(f'[OK] {ico_path}')

    master_path.unlink()
    return pngs[512]


# ── 2. standalone vector badge (hand-written SVG, same geometry) ──────────
def svg_path_d(xs, ys):
    pts = list(zip(xs, ys))
    d = f'M {pts[0][0]:.2f} {pts[0][1]:.2f} '
    d += ' '.join(f'L {x:.2f} {y:.2f}' for x, y in pts[1:])
    return d


def build_svg():
    wx, wy = wave_xy()
    wave_d = svg_path_d(wx, wy)

    bars_svg = '\n  '.join(
        f'<rect x="{x - BAR_W / 2:.2f}" y="{100 - (BAR_BASE + h):.2f}" '
        f'width="{BAR_W:.2f}" height="{h:.2f}" rx="1.4" fill="#ffffff"/>'
        for x, h in zip(BAR_X, BAR_H)
    )
    # SVG y grows downward; flip y for the wave/arrow to match matplotlib's
    # upward-positive axes used above.
    wave_d_flipped = svg_path_d(wx, 100 - wy)
    arrow_y = 100 - ARROW_Y

    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <rect x="4" y="4" width="92" height="92" rx="20" fill="{ACCENT}"/>
  <path d="{wave_d_flipped}" fill="none" stroke="#ffffff" stroke-width="{WAVE_LW * 100 / 72:.2f}"
        stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M {ARROW_X0} {arrow_y} L {ARROW_X1 - 3} {arrow_y}"
        stroke="#ffffff" stroke-width="3" stroke-linecap="round" opacity="0.9"/>
  <path d="M {ARROW_X1 - 5} {arrow_y - 4} L {ARROW_X1} {arrow_y} L {ARROW_X1 - 5} {arrow_y + 4}"
        fill="none" stroke="#ffffff" stroke-width="3" stroke-linecap="round"
        stroke-linejoin="round" opacity="0.9"/>
  {bars_svg}
</svg>
'''
    out = PUBLIC / 'dspkit_logo_icon.svg'
    out.write_text(svg, encoding='utf-8')
    print(f'[OK] {out}')

    # Print the pieces the Svelte component (no badge, currentColor/var(--accent)) needs.
    print('\n--- for DspkitLogo.svelte ---')
    print('wave path d=\n', wave_d_flipped)
    print('bars:')
    for x, h in zip(BAR_X, BAR_H):
        print(f'  x={x - BAR_W / 2:.2f} y={100 - (BAR_BASE + h):.2f} '
              f'width={BAR_W:.2f} height={h:.2f}')
    print(f'arrow shaft: M {ARROW_X0} {arrow_y} L {ARROW_X1 - 3} {arrow_y}')
    print(f'arrow head:  M {ARROW_X1 - 5} {arrow_y - 4} L {ARROW_X1} {arrow_y} L {ARROW_X1 - 5} {arrow_y + 4}')


if __name__ == '__main__':
    build_pngs()
    build_svg()
