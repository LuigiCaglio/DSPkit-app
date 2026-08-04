"""
Generate DSPkit logo design concepts.

Same approach as omakit-app-full/docs/design/generate_omakit_logos_v2.py:
draw a bunch of candidate marks with matplotlib, dump them to one PDF, pick
a favourite, then trace/export that one design into the final SVG/PNG/ICO
assets.

Unlike omakit (whose mark is literally its FRF output, with mode-order dot
markers), DSPkit is a general-purpose toolkit, so the motifs here are drawn
from what the GUI actually does: time series in, transform out. Every concept
is built around that time-domain <-> frequency-domain relationship, or one of
the specific tabs (Peaks, Filtering, Time-Freq) that make DSPkit's coverage
distinctive.
"""

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np

# Same accents as frontend/src/lib/theme.svelte.js -- previews line up with
# the real app themes instead of arbitrary brand colors.
COLORS = {
    'indigo (midnight)': '#6366f1',
    'ocean (teal)':       '#64ffda',
    'charcoal (blue)':    '#569cd6',
    'light (blue)':       '#2563eb',
    'neon (pink)':        '#ff006e',
}


def _base(ax):
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.set_aspect('equal')
    ax.axis('off')


def _label(ax, color, sub=None, y=9.3):
    ax.text(5, y, 'DSPkit', ha='center', va='bottom',
            fontsize=19, fontweight='bold', color=color)
    if sub:
        ax.text(5, 0.7, sub, ha='center', va='top',
                fontsize=10, color=color, alpha=0.7)


# ── 1. Wave -> Spectrum ───────────────────────────────────────────────────
# The one-line pitch for DSP: a time signal goes in, a spectrum comes out.
def draw_wave_to_spectrum(ax, color='#6366f1', with_text=True):
    _base(ax)

    t = np.linspace(0, 4.3, 220)
    envelope = np.clip(1.3 - t / 4.3, 0, 1)
    y = 5 + 2.3 * envelope * np.sin(2 * np.pi * 1.7 * t)
    ax.plot(t + 0.3, y, color=color, linewidth=2.4, solid_capstyle='round')

    # transform arrow
    ax.annotate('', xy=(5.85, 5), xytext=(4.95, 5),
                arrowprops=dict(arrowstyle='-|>', color=color, alpha=0.55, linewidth=1.6))

    # spectrum bars (FFT magnitude, tallest first, decaying)
    bar_x = np.array([6.3, 6.9, 7.5, 8.1, 8.7, 9.3])
    bar_h = np.array([2.6, 4.6, 3.4, 2.0, 1.1, 0.5])
    ax.bar(bar_x, bar_h, bottom=3, width=0.42, color=color, alpha=0.85)

    ax.plot([0.3, 9.7], [3, 3], color=color, linewidth=1, alpha=0.25)

    if with_text:
        _label(ax, color, sub='time → frequency')


# ── 2. Dual-domain split ──────────────────────────────────────────────────
# Same idea, cleaner/more geometric: a hard divider instead of an arrow.
def draw_dual_domain_split(ax, color='#6366f1', with_text=True):
    _base(ax)

    t = np.linspace(0, 4.3, 200)
    y = 5 + 2.2 * np.sin(2 * np.pi * 1.5 * t)
    ax.plot(t + 0.4, y, color=color, linewidth=2.4, solid_capstyle='round')
    ax.fill_between(t + 0.4, y, 5, color=color, alpha=0.10)

    ax.plot([5, 5], [2.2, 7.8], color=color, linewidth=1, alpha=0.3, linestyle=(0, (2, 2)))

    bar_x = np.array([5.9, 6.5, 7.1, 7.7, 8.3, 8.9, 9.5])
    bar_h = np.array([1.4, 3.0, 4.6, 3.6, 2.2, 1.2, 0.6])
    ax.bar(bar_x, bar_h, bottom=2.2, width=0.45, color=color, alpha=0.85)

    if with_text:
        _label(ax, color)


# ── 3. Windowed sine ───────────────────────────────────────────────────────
# A signal tapered by a window function -- both a universal "this is a
# signal" glyph and a real DSP concept (Hann/Hamming windowing).
def draw_windowed_sine(ax, color='#6366f1', with_text=True):
    _base(ax)

    t = np.linspace(0, 10, 300)
    window = np.sin(np.pi * t / 10) ** 1.5  # tapers to 0 at both ends
    y = 5 + 3.3 * window * np.sin(2 * np.pi * 1.1 * t)
    ax.plot(t, y, color=color, linewidth=2.3)

    env_hi = 5 + 3.3 * window
    env_lo = 5 - 3.3 * window
    ax.plot(t, env_hi, color=color, linewidth=1, linestyle='--', alpha=0.3)
    ax.plot(t, env_lo, color=color, linewidth=1, linestyle='--', alpha=0.3)
    ax.fill_between(t, env_lo, env_hi, color=color, alpha=0.06)

    if with_text:
        _label(ax, color)


# ── 4. Decaying oscillation ────────────────────────────────────────────────
# A damped time-domain response -- reads as "signal", also nods to
# decomposition/HHT instantaneous-amplitude tracking.
def draw_decaying_oscillation(ax, color='#6366f1', with_text=True):
    _base(ax)

    t = np.linspace(0, 10, 300)
    envelope = np.exp(-0.32 * t)
    y = 5 + 3.6 * envelope * np.cos(2 * np.pi * 0.85 * t)
    ax.plot(t, y, color=color, linewidth=2.2)

    ax.plot(t, 5 + 3.6 * envelope, color=color, linewidth=1, linestyle='--', alpha=0.3)
    ax.plot(t, 5 - 3.6 * envelope, color=color, linewidth=1, linestyle='--', alpha=0.3)
    ax.fill_between(t, 5 - 3.6 * envelope, 5 + 3.6 * envelope, color=color, alpha=0.07)
    ax.axhline(5, color=color, linewidth=0.8, alpha=0.15)

    if with_text:
        _label(ax, color)


# ── 5. Spectrum peaks (with markers) ───────────────────────────────────────
# A PSD-style curve with detected-peak dots -- directly reflects the Peaks
# tab under Spectral.
def draw_spectrum_peaks(ax, color='#6366f1', with_text=True, with_marker=True):
    _base(ax)

    f = np.linspace(0.3, 9.7, 400)

    def lorentzian(f0, zeta, amp):
        gamma = 2 * zeta * f0
        return amp / (1 + ((f - f0) / (gamma / 2)) ** 2)

    modes = [(2.4, 0.05, 0.55), (5.0, 0.025, 1.0), (7.6, 0.04, 0.7)]
    H = sum(lorentzian(f0, zeta, amp) for f0, zeta, amp in modes)
    y = 2 + 6 * (H / H.max())

    ax.plot(f, y, color=color, linewidth=2.2)
    ax.fill_between(f, y, 2, color=color, alpha=0.12)
    ax.axhline(2, color=color, linewidth=1, alpha=0.2, linestyle='--')

    if with_marker:
        for f0, zeta, amp in modes:
            idx = np.argmin(np.abs(f - f0))
            ax.plot(f[idx], y[idx], 'o', color=color, markersize=6.5, zorder=10,
                    markerfacecolor='white', markeredgewidth=1.4, markeredgecolor=color)

    if with_text:
        _label(ax, color)


# ── 6. Equalizer bars ──────────────────────────────────────────────────────
# The most universal "signal processing" pictogram there is. Reads well tiny.
def draw_equalizer_bars(ax, color='#6366f1', with_text=True):
    _base(ax)

    bar_x = np.array([1.5, 2.9, 4.3, 5.7, 7.1, 8.5])
    bar_h = np.array([3.0, 5.4, 6.6, 4.4, 5.8, 3.6])
    ax.bar(bar_x, bar_h, bottom=5 - bar_h / 2, width=0.9, color=color, alpha=0.88)

    if with_text:
        _label(ax, color)


# ── 7. Chirp signal ─────────────────────────────────────────────────────────
# Frequency sweeps upward over time -- distinct silhouette, nods to the
# Time-Freq tab (STFT/CWT/WVD all exist to track exactly this).
def draw_chirp_signal(ax, color='#6366f1', with_text=True):
    _base(ax)

    t = np.linspace(0, 10, 500)
    inst_f = 0.35 + 0.16 * t
    phase = 2 * np.pi * np.cumsum(inst_f) * (t[1] - t[0])
    y = 5 + 3.2 * np.sin(phase)
    ax.plot(t, y, color=color, linewidth=2.1)
    ax.fill_between(t, y, 5, color=color, alpha=0.06)

    if with_text:
        _label(ax, color)


# ── 8. Filter response ─────────────────────────────────────────────────────
# A lowpass Bode magnitude curve with a cutoff marker -- nods to Filtering.
def draw_filter_response(ax, color='#6366f1', with_text=True):
    _base(ax)

    f = np.linspace(0.2, 9.8, 400)
    fc = 5.0
    H = 1 / np.sqrt(1 + (f / fc) ** 6)  # steep-ish lowpass
    y = 2 + 6 * H

    ax.plot(f, y, color=color, linewidth=2.4)
    ax.fill_between(f, y, 2, color=color, alpha=0.12)
    ax.axhline(2, color=color, linewidth=1, alpha=0.25, linestyle='--')
    ax.axvline(fc, color=color, linewidth=1, alpha=0.3, linestyle=(0, (2, 2)))
    idx = np.argmin(np.abs(f - fc))
    ax.plot(fc, y[idx], 'o', color=color, markersize=6.5, zorder=10,
            markerfacecolor='white', markeredgewidth=1.4, markeredgecolor=color)

    if with_text:
        _label(ax, color, sub='lowpass')


# ── 9. Spectrogram waterfall ────────────────────────────────────────────────
# Stacked windows at different times -- the STFT idea, visually.
def draw_spectrogram_waterfall(ax, color='#6366f1', with_text=True):
    _base(ax)

    f = np.linspace(1, 9, 150)
    offsets = [2.2, 3.6, 5.0, 6.4]
    centers = [7.5, 6.2, 5.0, 4.2]
    for i, (offset, fc) in enumerate(zip(offsets, centers)):
        alpha_val = 1.0 - i * 0.16
        H = 1 / (1 + ((f - fc) / 0.7) ** 2)
        y = offset + 1.3 * H
        ax.plot(f, y, color=color, linewidth=1.7, alpha=alpha_val)
        ax.fill_between(f, y, offset, color=color, alpha=0.08 * alpha_val)

    if with_text:
        _label(ax, color, sub='STFT')


CONCEPTS = [
    ('Wave -> Spectrum',      draw_wave_to_spectrum),
    ('Dual-domain split',     draw_dual_domain_split),
    ('Windowed sine',         draw_windowed_sine),
    ('Decaying oscillation',  draw_decaying_oscillation),
    ('Spectrum peaks',        draw_spectrum_peaks),
    ('Equalizer bars',        draw_equalizer_bars),
    ('Chirp signal',          draw_chirp_signal),
    ('Filter response',       draw_filter_response),
    ('Spectrogram waterfall', draw_spectrogram_waterfall),
]


def create_logo_pdf(filename='dspkit_logo_concepts.pdf'):
    with PdfPages(filename) as pdf:
        # One page per pair of concepts, one row per concept, one column per color.
        color_items = list(COLORS.items())[:4]
        for i in range(0, len(CONCEPTS), 2):
            pair = CONCEPTS[i:i + 2]
            fig = plt.figure(figsize=(11, 5.6))
            fig.suptitle(f"DSPkit Logo Concepts — {' & '.join(name for name, _ in pair)}",
                         fontsize=14, fontweight='bold', y=0.99)
            for row, (name, draw_func) in enumerate(pair):
                for col, (cname, color) in enumerate(color_items):
                    ax = plt.subplot(2, 4, row * 4 + col + 1)
                    draw_func(ax, color=color)
                    if col == 0:
                        ax.set_title(name, fontsize=9, loc='left')
            plt.tight_layout()
            pdf.savefig(fig, bbox_inches='tight')
            plt.close()

        # Dark-mode page: best 4 concepts on a dark background.
        picks = [draw_wave_to_spectrum, draw_spectrum_peaks, draw_chirp_signal, draw_filter_response]
        light_colors = ['#818cf8', '#5eead4', '#93c5fd', '#ff5c9d']
        dark_bg = '#0f1117'
        fig = plt.figure(figsize=(11, 8.5))
        fig.patch.set_facecolor(dark_bg)
        fig.suptitle('DSPkit Logo Concepts — Dark Mode (top picks)',
                     fontsize=16, fontweight='bold', y=0.98, color='white')
        for i, draw_func in enumerate(picks):
            for j, color in enumerate(light_colors):
                ax = plt.subplot(4, 4, i * 4 + j + 1)
                ax.set_facecolor(dark_bg)
                draw_func(ax, color=color)
                if j == 0:
                    ax.text(0.02, 0.98, draw_func.__name__.replace('draw_', ''),
                            transform=ax.transAxes, fontsize=8, va='top', ha='left', color='white')
        plt.tight_layout()
        pdf.savefig(fig, bbox_inches='tight', facecolor=dark_bg)
        plt.close()

        # Small-size / icon-only page (no wordmark, thicker strokes as a proxy
        # for how they'll read at 16-32px).
        fig = plt.figure(figsize=(11, 8.5))
        fig.suptitle('DSPkit Logo Concepts — Icon Only (favicon proxy)',
                     fontsize=16, fontweight='bold', y=0.98)
        icon_picks = CONCEPTS  # all 9
        for i, (name, draw_func) in enumerate(icon_picks):
            ax = plt.subplot(3, 3, i + 1)
            draw_func(ax, color=COLORS['indigo (midnight)'], with_text=False)
            ax.set_title(name, fontsize=9)
        plt.tight_layout()
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()

        print(f'[OK] wrote {filename}')
        print(f'  {len(CONCEPTS)} concepts x {len(color_items)} theme colors, '
              f'+ dark-mode page + icon-only page')


if __name__ == '__main__':
    create_logo_pdf('dspkit_logo_concepts.pdf')
