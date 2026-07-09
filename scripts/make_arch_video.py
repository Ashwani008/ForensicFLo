#!/usr/bin/env python3
"""
Forensic Flo – Architecture Animation
Output : forensic_flo_arch.mp4  (9 s · 1920×1080 · 30 fps)
Run    : python scripts/make_arch_video.py

Requires: matplotlib (already pulled in by ultralytics/torch)
          ffmpeg on PATH (already required by the project)
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.animation import FuncAnimation, FFMpegWriter

# ── palette ───────────────────────────────────────────────────────────────────
BG    = "#050d1a"
CYAN  = "#00d4ff"
GREEN = "#39ff14"
ORNG  = "#ff8c42"
PURP  = "#b06eff"
YEL   = "#ffd700"
RED   = "#ff3860"
LITE  = "#dce8f5"
DARK  = "#0a1628"
DIM   = "#0d1a30"

# ── canvas  (19.2 × 10.8 in @ 100 dpi  =  1920 × 1080 px) ───────────────────
FPS, DUR = 30, 9
N        = FPS * DUR          # 270 frames
W, H     = 192.0, 108.0       # logical coordinate space

fig = plt.figure(figsize=(19.2, 10.8), dpi=100, facecolor=BG)
ax  = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, W)
ax.set_ylim(0, H)
ax.axis("off")
ax.set_facecolor(BG)

# ── helpers ───────────────────────────────────────────────────────────────────
pool: list = []

def _reg(a):
    pool.append(a)
    return a

def fr(s: float) -> int:
    return max(1, int(s * FPS))

def ease(x: float) -> float:
    x = float(np.clip(x, 0.0, 1.0))
    return x * x * (3.0 - 2.0 * x)

def ramp(frame: int, t0: float, t1: float) -> float:
    if frame < fr(t0):  return 0.0
    if frame >= fr(t1): return 1.0
    return ease((frame - fr(t0)) / (fr(t1) - fr(t0)))

def bx(cx, cy, w, h, fc=DIM, ec=CYAN, lw=1.5):
    p = FancyBboxPatch(
        (cx - w / 2, cy - h / 2), w, h,
        boxstyle="round,pad=0.5",
        facecolor=fc, edgecolor=ec,
        linewidth=lw, zorder=5, alpha=0.0,
    )
    ax.add_patch(p)
    return _reg(p)

def tx(cx, cy, s, fs, col=LITE, bold=True,
       ha="center", va="center", zorder=7):
    t = ax.text(
        cx, cy, s, ha=ha, va=va,
        fontsize=fs, color=col,
        fontweight="bold" if bold else "normal",
        fontfamily="monospace", zorder=zorder, alpha=0.0,
    )
    return _reg(t)

def arr(x1, y1, x2, y2, col=CYAN, lw=2.0):
    a = FancyArrowPatch(
        (x1, y1), (x2, y2),
        arrowstyle="->", mutation_scale=14,
        color=col, linewidth=lw,
        zorder=4, alpha=0.0,
    )
    ax.add_patch(a)
    return _reg(a)

# ── layout ────────────────────────────────────────────────────────────────────
#  Stage:   Media(0)  Extract(1)  Models(2)  Index(3)  Search(4)
X  = [16,   46,   88,   130,   168]
CY = 50.0

MY = [82.0, 66.0, 38.0, 22.0]           # model y-centres (top → bottom)
MC = [CYAN, GREEN, ORNG, PURP]           # model accent colours
ML = [
    "Whisper   |   Speech-to-Text",
    "YAMNet    |   Sound Events",
    "YOLOv8    |   Object Detection",
    "BLIP      |   Scene Captioning",
]

BW, BH = 26.0, 13.0    # standard box dims
MW, MH = 36.0, 11.0    # model box dims

# ── build every artist (all start invisible) ──────────────────────────────────

# title bar
ti_bg = bx(W / 2, H - 5.5, 118, 9, DARK, CYAN, 1.5)
ti_tx = tx(W / 2, H - 5.5, "FORENSIC FLO  /  AI Pipeline Architecture", 18, CYAN)

# --- raw media ---
me_bg = bx(X[0], CY,      BW, 50, DIM, CYAN, 1.2)
me_hd = tx(X[0], CY + 21, "RAW  MEDIA", 13, CYAN)
cc_bx = bx(X[0], CY + 10, 22, 9,  "#071525", CYAN,  1.0)
cc_tx = tx(X[0], CY + 10, "CCTV / VMS", 11, LITE)
bw_bx = bx(X[0], CY +  0, 22, 9,  "#071525", GREEN, 1.0)
bw_tx = tx(X[0], CY +  0, "Body-Worn Cam", 11, LITE)
au_bx = bx(X[0], CY - 10, 22, 9,  "#071525", ORNG,  1.0)
au_tx = tx(X[0], CY - 10, "Radio / Audio", 11, LITE)

# arrow: media → extract
a_me  = arr(X[0] + BW / 2, CY, X[1] - BW / 2, CY)

# --- extraction ---
ex_bx = bx(X[1], CY,       BW, BH, "#060f1e", CYAN, 1.5)
ex_t1 = tx(X[1], CY + 2.5, "ffmpeg", 13, CYAN)
ex_t2 = tx(X[1], CY - 3.0, "Audio / Frame\nExtraction", 10, LITE, bold=False)

# arrows: extract → models
a_em  = [arr(X[1] + BW / 2, CY, X[2] - MW / 2, my, col=mc)
         for my, mc in zip(MY, MC)]

# --- AI models ---
m_bx  = [bx(X[2], my, MW, MH, "#060e22", mc, 1.5) for my, mc in zip(MY, MC)]
m_tx  = [tx(X[2], my, ml, 10.5, mc) for my, ml, mc in zip(MY, ML, MC)]

# arrows: models → index
a_mi  = [arr(X[2] + MW / 2, my, X[3] - BW / 2, CY, col=mc)
         for my, mc in zip(MY, MC)]

# --- unified index ---
ix_bg = bx(X[3], CY,      BW, 50, "#051508", GREEN, 2.0)
ix_hd = tx(X[3], CY + 21, "UNIFIED  INDEX", 13, GREEN)
ix_l1 = tx(X[3], CY + 10, "Speech tokens + timestamps",  10, LITE, bold=False)
ix_l2 = tx(X[3], CY +  3, "Sound event labels",          10, LITE, bold=False)
ix_l3 = tx(X[3], CY -  4, "Object detection labels",     10, LITE, bold=False)
ix_l4 = tx(X[3], CY - 11, "Natural-language captions",   10, LITE, bold=False)

# arrow: index → search
a_is  = arr(X[3] + BW / 2, CY, X[4] - BW / 2 - 2, CY, col=YEL, lw=2.5)

# --- search UI ---
sr_bg = bx(X[4], CY,      BW + 8, 50, "#130e00", YEL, 2.0)
sr_hd = tx(X[4], CY + 21, "SEMANTIC  SEARCH", 13, YEL)
qr_bx = bx(X[4], CY +  9, 30, 8,  "#0c0900", YEL, 1.0)
qr_tx = tx(X[4], CY +  9, '"yellow backpack"', 11, YEL)
rs_1  = tx(X[4], CY +  0, "14 matches found", 11, GREEN)
rs_2  = tx(X[4], CY -  8, "Jump -> 02:14:33",  11, CYAN)

# tagline
tg_bg = bx(W / 2, 6.5, 138, 10, "#130005", RED, 2.0)
tg_tx = tx(W / 2, 6.5, "Hours of manual scrubbing   ->   2-second query", 16, RED)

# ── schedule: artist -> (fade_in_start_sec, fade_in_end_sec) ─────────────────
S: dict = {
    ti_bg: (0.0, 0.7),    ti_tx: (0.1, 0.8),

    me_bg: (0.5, 1.2),    me_hd: (0.6, 1.3),
    cc_bx: (0.7, 1.3),    cc_tx: (0.7, 1.3),
    bw_bx: (0.9, 1.5),    bw_tx: (0.9, 1.5),
    au_bx: (1.1, 1.7),    au_tx: (1.1, 1.7),

    a_me:  (1.6, 2.1),

    ex_bx: (1.8, 2.3),    ex_t1: (1.9, 2.4),    ex_t2: (2.0, 2.5),

    a_em[0]: (2.3, 2.8),  m_bx[0]: (2.5, 3.0),  m_tx[0]: (2.5, 3.0),
    a_em[1]: (2.7, 3.2),  m_bx[1]: (2.9, 3.4),  m_tx[1]: (2.9, 3.4),
    a_em[2]: (3.1, 3.6),  m_bx[2]: (3.3, 3.8),  m_tx[2]: (3.3, 3.8),
    a_em[3]: (3.5, 4.0),  m_bx[3]: (3.7, 4.2),  m_tx[3]: (3.7, 4.2),

    a_mi[0]: (4.0, 4.5),  a_mi[1]: (4.1, 4.6),
    a_mi[2]: (4.2, 4.7),  a_mi[3]: (4.3, 4.8),

    ix_bg: (4.3, 4.9),    ix_hd: (4.4, 5.0),
    ix_l1: (4.6, 5.1),    ix_l2: (4.7, 5.2),
    ix_l3: (4.8, 5.3),    ix_l4: (4.9, 5.4),

    a_is:  (5.4, 5.9),
    sr_bg: (5.7, 6.2),    sr_hd: (5.8, 6.3),
    qr_bx: (6.0, 6.5),    qr_tx: (6.1, 6.6),
    rs_1:  (6.5, 7.0),    rs_2:  (6.8, 7.3),

    tg_bg: (7.3, 8.0),    tg_tx: (7.4, 8.1),
}

# ── animation ─────────────────────────────────────────────────────────────────
def init():
    for a in pool:
        a.set_alpha(0.0)
    return pool

def update(frame):
    for artist, (t0, t1) in S.items():
        artist.set_alpha(ramp(frame, t0, t1))
    return pool

anim = FuncAnimation(
    fig, update, frames=N,
    init_func=init, blit=False, interval=1000 / FPS,
)

out = Path(__file__).resolve().parent.parent / "forensic_flo_arch.mp4"
writer = FFMpegWriter(
    fps=FPS, bitrate=6000,
    extra_args=["-vcodec", "libx264", "-pix_fmt", "yuv420p"],
)

print(f"Rendering {N} frames at 1920x1080 ...")
anim.save(
    str(out), writer=writer, dpi=100,
    progress_callback=lambda i, n: print(f"  frame {i}/{n}", end="\r", flush=True),
)
print(f"\nDone  ->  {out}")
