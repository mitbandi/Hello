import json, math, subprocess, sys, re, functools
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1080, 1920, 30
MAIN_END = 135.0
DISC_END = 141.0
TOTAL = 146.5
NFRAMES = int(round(TOTAL * FPS))
PH = 960  # split panel height

def hexc(h): h = h.lstrip('#'); return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
C1, C2, C3, C4, C5 = map(hexc, ['#325e3c', '#0e9a52', '#0e7949', '#6fc066', '#d2e8c5'])
WHITE = (255, 255, 255); DARK = (10, 28, 17); HOT = (240, 120, 40)

FD = 'font/package/'
FW = {'400': '400Regular/Montserrat_400Regular.ttf', '500': '500Medium/Montserrat_500Medium.ttf',
      '600': '600SemiBold/Montserrat_600SemiBold.ttf', '700': '700Bold/Montserrat_700Bold.ttf',
      '800': '800ExtraBold/Montserrat_800ExtraBold.ttf', '900': '900Black/Montserrat_900Black.ttf'}
@functools.lru_cache(None)
def font(w, size): return ImageFont.truetype(FD + FW[w], size)

def clamp(x, a=0, b=1): return max(a, min(b, x))
def eo(x): x = clamp(x); return 1 - (1 - x) ** 3
def eio(x): x = clamp(x); return 3 * x * x - 2 * x * x * x
def eback(x, s=1.7):
    x = clamp(x); x -= 1; return x * x * ((s + 1) * x + s) + 1
def prog(t, t0, d=0.4): return clamp((t - t0) / d)

def rgba(c, a): return (c[0], c[1], c[2], int(255 * clamp(a)))

# ---------------------------------------------------------------- text helpers
def text(d, xy, s, size, w='800', fill=WHITE, a=1.0, anchor='mm', spacing=0):
    if a <= 0: return
    f = font(w, size)
    if spacing:
        # manual letter spacing
        widths = [f.getlength(ch) for ch in s]
        total = sum(widths) + spacing * (len(s) - 1)
        x0 = xy[0] - (total / 2 if anchor[0] == 'm' else (total if anchor[0] == 'r' else 0))
        for ch, wd in zip(s, widths):
            d.text((x0, xy[1]), ch, font=f, fill=rgba(fill, a), anchor='l' + anchor[1]); x0 += wd + spacing
        return
    d.text(xy, s, font=f, fill=rgba(fill, a), anchor=anchor)

def rise(t, t0, dist=40, d=0.45):
    p = eo(prog(t, t0, d)); return p, (1 - p) * dist

def pill(d, cx, cy, s, size, w='800', bg=C2, fg=WHITE, a=1.0, padx=28, pady=16, r=None):
    f = font(w, size); tw = f.getlength(s); th = size
    box = (cx - tw / 2 - padx, cy - th / 2 - pady, cx + tw / 2 + padx, cy + th / 2 + pady)
    d.rounded_rectangle(box, radius=r if r is not None else (th / 2 + pady), fill=rgba(bg, a))
    text(d, (cx, cy + 1), s, size, w, fg, a)
    return box

def paste_rgba(dst, src, cx, cy, scale=1.0, alpha=1.0):
    if alpha <= 0.003 or scale <= 0.01: return
    if abs(scale - 1) > 1e-3:
        src = src.resize((max(1, int(src.width * scale)), max(1, int(src.height * scale))), Image.BILINEAR)
    if alpha < 0.999:
        a = src.getchannel('A').point(lambda v: int(v * alpha)); src = src.copy(); src.putalpha(a)
    x, y = int(cx - src.width / 2), int(cy - src.height / 2)
    if dst.mode == 'RGBA': dst.alpha_composite(src, (max(0, x), max(0, y)), (max(0, -x), max(0, -y)))
    else: dst.paste(src, (x, y), src)

def inr(n):  # indian grouping
    s = str(int(n))
    if len(s) <= 3: return s
    return re.sub(r'(\d)(?=(\d\d)+$)', r'\1,', s[:-3]) + ',' + s[-3:]

# ---------------------------------------------------------------- panel background
def make_panel_bg():
    h = PH + 120
    y = np.linspace(0, 1, h)[:, None]; x = np.linspace(0, 1, W)[None, :]
    top = np.array(C1, float); bot = np.array((14, 34, 22), float)
    g = top[None, None] * (1 - y[..., None]) * 0.9 + bot[None, None] * (y[..., None] * 0.9 + 0.1)
    glow = np.exp(-(((x - 0.8) ** 2) / 0.08 + ((y - 0.15) ** 2) / 0.05))[..., None] * np.array(C2, float) * 0.35
    g = np.clip(g + glow, 0, 255).astype(np.uint8)
    im = Image.fromarray(g, 'RGB'); d = ImageDraw.Draw(im, 'RGBA')
    for gx in range(0, W + 1, 60): d.line([(gx, 0), (gx, h)], fill=(111, 192, 102, 18), width=1)
    for gy in range(0, h + 1, 60): d.line([(0, gy), (W, gy)], fill=(111, 192, 102, 18), width=1)
    return im
PANEL_BG = make_panel_bg()

def panel_base(t):
    off = int((t * 12) % 60)
    return PANEL_BG.crop((0, off, W, off + PH)).copy()

def header(d, t, t0, label, y=95, size=40):
    p, dy = rise(t, t0)
    sp = 6
    while font('800', size).getlength(label) + sp * len(label) > 700: size -= 2; sp = 4
    text(d, (W / 2, y + dy), label, size, '800', C4, p, spacing=sp)
    wl = 160 * eo(prog(t, t0 + 0.15, 0.5))
    d.rectangle((W / 2 - wl / 2, y + 36 + dy, W / 2 + wl / 2, y + 42 + dy), fill=rgba(C2, p))

# ---------------------------------------------------------------- graphics (top panel)
def g_clients(d, im, t):
    if t < 9.0:
        header(d, t, 2.5, 'SUPPLIES PARTS TO')
        chips = [('ROLLS-ROYCE', 3.0, 300), ('GE', 4.3, 470), ('BOEING', 6.9, 640)]
        for s, t0, y in chips:
            p = prog(t, t0, 0.45); sc = eback(p)
            if p > 0:
                f = font('900', 92); tw = f.getlength(s)
                x0 = W / 2 - tw / 2 - 50; x1 = W / 2 + tw / 2 + 50
                xs = (1 - eo(p)) * -200
                d.rounded_rectangle((x0 + xs, y - 75, x1 + xs, y + 75), 26, fill=rgba(WHITE, 0.08 * p), outline=rgba(C4, p), width=4)
                text(d, (W / 2 + xs, y + 2), s, 92, '900', WHITE, p)
        p = prog(t, 7.8, 0.5)
        text(d, (W / 2, 800 + (1 - eo(p)) * 30), '+ MANY MORE GLOBAL OEMs', 40, '700', C5, p, spacing=3)
    else:
        p = eo(prog(t, 9.1, 0.5))
        text(d, (W / 2, 300 + (1 - p) * 30), 'THIS IS THE STORY OF', 44, '700', C5, p, spacing=8)
        q = prog(t, 10.2, 0.5); sc = 0.7 + 0.3 * eback(q)
        if q > 0:
            lay = title_img('AZAD', 190)
            paste_rgba(im, lay, W / 2, 470, sc, eo(q))
            lay2 = title_img('ENGINEERING', 88, C4)
            paste_rgba(im, lay2, W / 2, 625, sc, eo(prog(t, 10.5, 0.4)))
            wl = 520 * eo(prog(t, 10.6, 0.5))
            d.rectangle((W / 2 - wl / 2, 700, W / 2 + wl / 2, 710), fill=rgba(C2, 1))

@functools.lru_cache(None)
def title_img(s, size, col=WHITE, w='900'):
    f = font(w, size); tw = int(f.getlength(s)) + 40; th = int(size * 1.4)
    im = Image.new('RGBA', (tw, th), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.text((tw / 2, th / 2), s, font=f, fill=col + (255,), anchor='mm')
    return im

def gear(d, cx, cy, r, ang, col, a, teeth=10):
    pts = []
    for i in range(teeth * 4):
        th = ang + i * 2 * math.pi / (teeth * 4)
        rr = r if (i % 4) in (0, 1) else r * 0.8
        pts.append((cx + rr * math.cos(th), cy + rr * math.sin(th)))
    d.polygon(pts, fill=rgba(col, a))
    d.ellipse((cx - r * 0.35, cy - r * 0.35, cx + r * 0.35, cy + r * 0.35), fill=rgba(C1, a))

def g_founder(d, im, t):
    header(d, t, 11.7, 'THE FOUNDER')
    a = eo(prog(t, 11.8, 0.6))
    gear(d, 930, 760, 120, t * 0.6, C3, 0.55 * a, 12)
    gear(d, 790, 860, 70, -t * 1.03 + 0.2, C1, 0.7 * a, 8)
    p = prog(t, 12.4, 0.5)
    if p > 0: paste_rgba(im, title_img('Rakesh', 120), W / 2, 260, 0.8 + 0.2 * eback(p), eo(p))
    p = prog(t, 13.4, 0.5)
    if p > 0: paste_rgba(im, title_img('Chopdar', 120, C4), W / 2, 390, 0.8 + 0.2 * eback(p), eo(p))
    p = prog(t, 14.4, 0.5)
    if p > 0:
        d.rounded_rectangle((140, 500, 940, 700), 30, fill=rgba(WHITE, 0.07 * p), outline=rgba(C2, p), width=3)
        n = int(round(10 + 2 * eo(prog(t, 14.6, 0.8))))
        text(d, (W / 2, 575), f'10–{n} YEARS', 84, '900', WHITE, eo(p))
        text(d, (W / 2, 655), 'ON THE FACTORY FLOOR', 34, '700', C5, eo(prog(t, 15.7, 0.4)), spacing=4)
    p, dy = rise(t, 17.4)
    text(d, (W / 2, 790 + dy), "Father's small precision", 40, '600', C5, p)
    text(d, (W / 2, 845 + dy), 'castings factory', 40, '600', C5, p)

def g_cnc(d, im, t):
    header(d, t, 24.3, 'THE BEGINNING')
    p = prog(t, 24.6, 0.5)
    # CNC machine icon
    if p > 0:
        a = eo(p); cx, cy = 300, 470; s = 0.7 + 0.3 * eback(p)
        def R(x0, y0, x1, y1): return (cx + x0 * s, cy + y0 * s, cx + x1 * s, cy + y1 * s)
        d.rounded_rectangle(R(-190, -230, 190, 230), 22, fill=rgba(C5, a))
        d.rounded_rectangle(R(-150, -190, 150, 80), 14, fill=rgba(C1, a))
        d.rectangle(R(-20, -190, 20, -60 + 25 * math.sin(t * 6)), fill=rgba((180, 190, 185), a))
        d.polygon([(cx - 12 * s, cy + (-60 + 25 * math.sin(t * 6)) * s), (cx + 12 * s, cy + (-60 + 25 * math.sin(t * 6)) * s), (cx, cy + (-30 + 25 * math.sin(t * 6)) * s)], fill=rgba((220, 225, 220), a))
        d.rectangle(R(-110, 40, 110, 70), fill=rgba(C3, a))
        for k in range(6):  # sparks
            ang = t * 9 + k; rr = 30 + (t * 140 + k * 23) % 50
            sx = cx + math.cos(ang) * rr * s; sy = cy + (-20 + 25 * math.sin(t * 6)) * s + math.sin(ang) * rr * 0.4 * s
            d.ellipse((sx - 3, sy - 3, sx + 3, sy + 3), fill=rgba((255, 210, 120), a * 0.9))
        d.rounded_rectangle(R(-150, 110, 150, 170), 10, fill=rgba(C2, a))
        text(d, (cx, cy + 140 * s), 'CNC', int(40 * s), '900', WHITE, a)
    p = prog(t, 24.8, 0.4)
    if p > 0: paste_rgba(im, title_img('1', 260, C4), 720, 360, 0.6 + 0.4 * eback(p), eo(p))
    p, dy = rise(t, 25.5)
    text(d, (720, 540 + dy), 'SINGLE CNC', 54, '900', WHITE, p)
    text(d, (720, 600 + dy), 'MACHINE', 54, '900', WHITE, p)
    p = prog(t, 26.6, 0.5)
    if p > 0:
        pill(d, W / 2, 790 + (1 - eo(p)) * 30, 'AZAD ENGINEERING IS BORN · 2008', 36, '800', C2, WHITE, eo(p))
    p, dy = rise(t, 29.6)
    text(d, (W / 2, 870 + dy), 'Innovating from day one', 34, '600', C5, p)

ENG = Image.open('engine.jpg').convert('RGB')
ENG_PAD = Image.new('RGB', (2000, 1148), (34, 34, 34)); ENG_PAD.paste(ENG, (0, 167))
VP = (0, 150, 1080, 770)  # viewport in panel
def g_engine(d, im, t):
    header(d, t, 38.7, '3D ROTATING AIRFOILS' if t < 41.7 else 'INSIDE AN ENGINE', 80)
    vw, vh = VP[2] - VP[0], VP[3] - VP[1]
    # camera: start tight on turbine rotor, pull back to full engine
    z0 = (1355, 410 + 167, 620); z1 = (1000, 574, 2000)
    k = eio(prog(t, 41.8, 1.3))
    drift = 1 - 0.06 * clamp((t - 38.6) / 3.2)  # slow push-in while tight
    cx = z0[0] + (z1[0] - z0[0]) * k; cy = z0[1] + (z1[1] - z0[1]) * k
    bw = (z0[2] * drift) + (z1[2] - z0[2] * drift) * k; bh = bw * vh / vw
    cx = clamp(cx, bw / 2, 2000 - bw / 2); cy = clamp(cy, bh / 2, 1148 - bh / 2)
    box = (max(0.0, cx - bw / 2), max(0.0, cy - bh / 2), min(2000.0, cx + bw / 2), min(1148.0, cy + bh / 2))
    view = ENG_PAD.resize((vw, vh), Image.BILINEAR, box=box)
    a = eo(prog(t, 38.6, 0.5))
    if a < 1: view = Image.blend(Image.new('RGB', (vw, vh), (34, 34, 34)), view, a)
    vd = ImageDraw.Draw(view, 'RGBA')
    sx = vw / bw
    def vx(x): return (x - box[0]) * sx
    # section highlights (image coords: cold 40-930, hot 1000-1960)
    pc = prog(t, 44.5, 0.4); ph = prog(t, 45.4, 0.4); pend = prog(t, 46.6, 0.5)
    if pc > 0:
        dim_hot = eo(pc) * (1 - eo(ph)); dim_cold = eo(ph) * (1 - eo(pend))
        if dim_hot > 0: vd.rectangle((vx(965), 0, vw, vh), fill=(0, 0, 0, int(150 * dim_hot)))
        if dim_cold > 0: vd.rectangle((0, 0, vx(965), vh), fill=(0, 0, 0, int(150 * dim_cold)))
    # airfoil callout while tight
    pa = prog(t, 39.6, 0.4) * (1 - prog(t, 41.6, 0.3))
    if pa > 0:
        fx, fy = vx(1355), (410 + 167 - box[1]) * sx
        r = 230 * (0.8 + 0.2 * eback(prog(t, 39.6, 0.5)))
        vd.ellipse((fx - r, fy - r, fx + r, fy + r), outline=rgba(C4, pa), width=6)
    im.paste(view, (VP[0], VP[1]))
    d.rectangle((0, VP[1] - 3, W, VP[1]), fill=rgba(C4, 0.8)); d.rectangle((0, VP[3], W, VP[3] + 3), fill=rgba(C4, 0.8))
    if pa > 0: pill(d, W / 2, VP[3] - 60, 'TURBINE ROTOR · 3D AIRFOILS', 34, '800', C2, WHITE, pa)
    p = prog(t, 44.5, 0.5)
    if p > 0:
        e = eo(p); hl = 1 - 0.45 * eo(ph) * (1 - eo(pend))
        d.rounded_rectangle((60, 800, 60 + 465 * e, 880), 18, fill=rgba(C5, e * hl))
        text(d, (292, 840), 'COLD SECTION', 36, '900', C1, prog(t, 44.7, 0.3))
    if ph > 0:
        e = eo(ph); fl = 0.85 + 0.15 * math.sin(t * 12)
        col = (int(230 * fl + 20), int(100 * fl), 30)
        d.rounded_rectangle((555, 800, 555 + 465 * e, 880), 18, fill=rgba(col, e))
        text(d, (787, 840), 'HOT SECTION', 36, '900', WHITE, prog(t, 45.6, 0.3))

def g_heat(d, im, t):
    header(d, t, 57.0, 'EXTREME CONDITIONS')
    a = eo(prog(t, 57.1, 0.5))
    tx, ty0, ty1 = 220, 190, 800
    d.rounded_rectangle((tx - 42, ty0, tx + 42, ty1), 42, fill=rgba((255, 255, 255), 0.12 * a), outline=rgba(C5, a), width=4)
    d.ellipse((tx - 75, ty1 - 60, tx + 75, ty1 + 90), fill=rgba(HOT, a), outline=rgba(C5, a), width=4)
    lvl = 0.12 + 0.18 * eo(prog(t, 57.9, 1.0)) + 0.15 * eo(prog(t, 59.1, 1.0)) + 0.5 * eo(prog(t, 63.6, 1.6))
    lvl = min(lvl, 0.96)
    top = ty1 - (ty1 - ty0 - 30) * lvl
    c = tuple(int(C4[i] * (1 - lvl) + (235, 70, 40)[i] * lvl) for i in range(3))
    d.rounded_rectangle((tx - 24, top, tx + 24, ty1 + 20), 24, fill=rgba(c, a))
    d.ellipse((tx - 58, ty1 - 40, tx + 58, ty1 + 72), fill=rgba(c, a))
    for k in range(9):
        yy = ty0 + 60 + k * 60
        d.line([(tx + 50, yy), (tx + 70 if k % 2 else tx + 85, yy)], fill=rgba(C5, a * 0.8), width=3)
    p, dy = rise(t, 57.9)
    pill(d, 650, 240 + dy, 'HIGH PRESSURE', 44, '900', C2, WHITE, p)
    p, dy = rise(t, 59.1)
    pill(d, 650, 360 + dy, 'HIGH HEAT', 44, '900', (205, 85, 35), WHITE, p)
    p = prog(t, 63.8, 0.4)
    if p > 0:
        v = 2500 * eo(prog(t, 63.9, 0.5)) + 500 * eo(prog(t, 64.4, 0.6))
        text(d, (650, 520), 'UP TO', 36, '700', C5, eo(p), spacing=4)
        paste_rgba(im, title_img(f'{inr(v)}°C', 130, WHITE), 650, 620, 0.85 + 0.15 * eback(p), eo(p))
        text(d, (650, 715), 'in the hot section', 36, '600', C5, eo(prog(t, 65.0, 0.4)))
    p, dy = rise(t, 66.3)
    text(d, (650, 830 + dy), '= EXTREMELY COMPLEX', 46, '900', C4, p)

def g_qualify(d, im, t):
    header(d, t, 69.1, 'THE QUALIFICATION BARRIER')
    p, dy = rise(t, 70.2)
    text(d, (W / 2, 230 + dy), 'Getting approved by global OEMs', 40, '700', C5, p)
    x0, x1, y = 130, 950, 420
    a = eo(prog(t, 70.4, 0.5))
    d.rounded_rectangle((x0, y - 12, x1, y + 12), 12, fill=rgba(WHITE, 0.15 * a))
    fill = 0.15 * eo(prog(t, 72.0, 2.5)) + 0.85 * eio(prog(t, 74.6, 2.0))
    d.rounded_rectangle((x0, y - 12, x0 + (x1 - x0) * fill, y + 12), 12, fill=rgba(C4, a))
    for k in range(13):
        xx = x0 + (x1 - x0) * k / 12; on = fill >= k / 12 - 1e-3
        d.ellipse((xx - 14, y - 14, xx + 14, y + 14), fill=rgba(C2 if on else C1, a), outline=rgba(C5, a), width=3)
    yr = int(round(12 * fill))
    if a > 0: text(d, (x0 + (x1 - x0) * fill, y - 60), f'YR {yr}', 32, '800', WHITE, a)
    p = prog(t, 76.3, 0.45)
    if p > 0:
        paste_rgba(im, title_img('12 YEARS', 150, WHITE), W / 2, 600, 0.8 + 0.2 * eback(p), eo(p))
        text(d, (W / 2, 710), 'TO GET QUALIFIED', 44, '800', C4, eo(prog(t, 77.0, 0.4)), spacing=4)
    p, dy = rise(t, 79.0)
    pill(d, W / 2, 830 + dy, 'AEROSPACE TECH SEGMENT', 36, '800', C2, WHITE, p)

def g_numbers(d, im, t):
    header(d, t, 89.1, 'AZAD ENGINEERING · TODAY')
    cards = [('REVENUE', 590, 91.7, 220), ('PROFIT AFTER TAX', 130, 92.9, 450), ('ORDER BOOK', 6500, 94.7, 680)]
    for lab, val, t0, y in cards:
        p = prog(t, t0, 0.45)
        if p <= 0: continue
        e = eo(p); xs = (1 - e) * 300
        d.rounded_rectangle((110 + xs, y - 95, 970 + xs, y + 95), 28, fill=rgba(WHITE, 0.08 * e), outline=rgba(C4, e), width=3)
        d.rounded_rectangle((110 + xs, y - 95, 126 + xs, y + 95), 8, fill=rgba(C2, e))
        text(d, (170 + xs, y - 40), lab, 34, '800', C5, e, anchor='lm')
        v = val * eo(prog(t, t0 + 0.1, 0.9))
        text(d, (170 + xs, y + 30), f'₹{inr(v)} Cr', 86, '900', WHITE, e, anchor='lm')
    p, dy = rise(t, 95.8)
    text(d, (W / 2, 840 + dy), 'Approx. figures', 26, '500', C5, p * 0.8)

def g_partners(d, im, t):
    if t < 104.5:
        p, dy = rise(t, 97.5)
        pill(d, W / 2, 170 + dy, 'JANUARY 2024', 40, '900', C2, WHITE, p)
        q = prog(t, 99.4, 0.5)
        if q > 0: paste_rgba(im, title_img('ROLLS-ROYCE', 128, WHITE), W / 2, 380, 0.8 + 0.2 * eback(q), eo(q))
        p, dy = rise(t, 100.2)
        text(d, (W / 2, 500 + dy), 'TIES UP WITH AZAD', 46, '800', C4, p, spacing=4)
        p = prog(t, 102.4, 0.5)
        if p > 0:
            e = eo(p)
            d.rounded_rectangle((120, 600, 960, 820), 30, fill=rgba(WHITE, 0.08 * e), outline=rgba(C4, e), width=3)
            # shield icon
            sx, sy = 230, 710
            d.polygon([(sx - 55, sy - 65), (sx + 55, sy - 65), (sx + 55, sy + 5), (sx, sy + 70), (sx - 55, sy + 5)], fill=rgba(C2, e))
            d.line([(sx - 25, sy), (sx - 5, sy + 22), (sx + 30, sy - 25)], fill=rgba(WHITE, e), width=10)
            text(d, (320, 670), 'LONG-TERM STRATEGIC', 40, '900', WHITE, e, anchor='lm')
            text(d, (320, 730), 'DEFENCE PARTNERSHIP', 40, '900', C4, e, anchor='lm')
    else:
        p, dy = rise(t, 104.6)
        text(d, (W / 2, 150 + dy), 'ALSO TIED UP WITH', 36, '700', C5, p, spacing=6)
        q = prog(t, 104.7, 0.5)
        if q > 0:
            paste_rgba(im, title_img('MITSUBISHI', 128, WHITE), W / 2, 270, 0.8 + 0.2 * eback(q), eo(q))
            text(d, (W / 2, 370), 'HEAVY INDUSTRIES', 44, '800', C4, eo(prog(t, 105.0, 0.4)), spacing=8)
        p = prog(t, 108.0, 0.5)
        if p > 0:
            e = eo(p)
            pill(d, 380, 520 + (1 - e) * 30, 'NOZZLES', 52, '900', C2, WHITE, e)
            text(d, (W / 2 + 38, 520 + (1 - e) * 30), '&', 52, '900', C5, e)
        p = prog(t, 108.6, 0.5)
        if p > 0:
            e = eo(p); pill(d, 730, 520 + (1 - e) * 30, 'VANES', 52, '900', C2, WHITE, e)
        p, dy = rise(t, 109.6)
        if p > 0:
            fl = 0.85 + 0.15 * math.sin(t * 10)
            pill(d, W / 2, 680 + dy, 'FOR THE HOT SECTION OF THE ENGINE', 34, '800', (int(220 * fl), int(95 * fl), 35), WHITE, p)
        p, dy = rise(t, 110.4)
        text(d, (W / 2, 820 + dy), 'Single-source supplier · 8-year deal', 34, '600', C5, p)

def g_growth(d, im, t):
    header(d, t, 120.9, 'THE SKY IS THE LIMIT')
    base = 760
    bars = [('25%', 0.55, 123.85, 300), ('30%', 0.70, 124.25, 540), ('35%', 0.88, 124.6, 780)]
    a = eo(prog(t, 121.2, 0.5))
    d.line([(150, base), (930, base)], fill=rgba(C5, a), width=4)
    for lab, hgt, t0, x in bars:
        p = eback(prog(t, t0, 0.55), 1.2)
        if p <= 0: continue
        h = 520 * hgt * p
        d.rounded_rectangle((x - 80, base - h, x + 80, base), 18, fill=rgba(C2 if lab != '35%' else C4, min(1, p)))
        text(d, (x, base - h - 45), lab, 60, '900', WHITE, min(1, p))
    p = prog(t, 122.9, 0.5)
    if p > 0:  # arrow
        e = eo(p)
        d.line([(200, 600), (200 + 640 * e, 600 - 380 * e)], fill=rgba(WHITE, 0.4 * e), width=6)
    p, dy = rise(t, 125.7)
    text(d, (W / 2, 820 + dy), 'GROWTH FOR THE NEXT 8–12 YEARS', 38, '900', C4, p)
    text(d, (W / 2, 880 + dy), "As per speaker's view · not a guarantee", 24, '500', C5, p * 0.75)

def factory(d, cx, cy, s, col, a):
    d.rectangle((cx - 40 * s, cy - 10 * s, cx + 40 * s, cy + 30 * s), fill=rgba(col, a))
    d.polygon([(cx - 40 * s, cy - 10 * s), (cx - 40 * s, cy - 35 * s), (cx - 13 * s, cy - 10 * s), (cx - 13 * s, cy - 35 * s), (cx + 14 * s, cy - 10 * s), (cx + 14 * s, cy - 35 * s), (cx + 40 * s, cy - 10 * s)], fill=rgba(col, a))
    d.rectangle((cx + 22 * s, cy - 60 * s, cx + 34 * s, cy - 20 * s), fill=rgba(col, a))

def g_capacity(d, im, t):
    header(d, t, 127.8, 'NEW FACTORIES')
    p = prog(t, 128.2, 0.4)
    if p > 0: factory(d, 200, 330, 1.6 * eback(p), C5, eo(p))
    text(d, (200, 440), 'TODAY', 30, '800', C5, eo(p), spacing=4)
    for k in range(10):
        q = prog(t, 129.5 + k * 0.07, 0.35)
        if q <= 0: continue
        cx = 470 + (k % 5) * 110; cy = 270 + (k // 5) * 140
        factory(d, cx, cy, 1.1 * eback(q), C4, eo(q))
    q = prog(t, 129.6, 0.5)
    if q > 0:
        paste_rgba(im, title_img('10X', 200, WHITE), W / 2, 640, 0.6 + 0.4 * eback(q), eo(q))
    p, dy = rise(t, 130.6)
    text(d, (W / 2, 790 + dy), 'THE SIZE OF CURRENT CAPACITY', 40, '900', C4, p)

SEGS = [  # (start, end, fn)
    (2.35, 11.55, g_clients), (11.55, 20.0, g_founder), (24.15, 31.3, g_cnc),
    (38.55, 49.65, g_engine), (56.8, 68.9, g_heat), (68.9, 79.95, g_qualify),
    (88.95, 97.35, g_numbers), (97.35, 111.75, g_partners), (119.7, 127.7, g_growth),
    (127.7, 132.0, g_capacity)]
TR = 0.45

def split_state(t):
    for s, e, fn in SEGS:
        if s - 0.01 <= t < e + TR:
            pin = eio(prog(t, s, TR)); pout = eio(prog(t, e, TR))
            # chained segments: no out-transition if next starts at e
            chained_out = any(abs(s2 - e) < 0.02 for s2, _, _ in SEGS)
            chained_in = any(abs(e2 - s) < 0.02 for _, e2, _ in SEGS)
            if chained_in: pin = 1.0
            if chained_out:
                if t >= e: continue
                pout = 0.0
            return pin * (1 - pout), fn, (t if t < e else e - 0.001)
    return 0.0, None, t

# ---------------------------------------------------------------- full-screen stickers
def stickers(d, im, t):
    # hook
    if 0.0 <= t < 2.9:
        p = prog(t, 0.15, 0.45); out = prog(t, 2.4, 0.4)
        a = eo(p) * (1 - out)
        if a > 0:
            paste_rgba(im, hook_img(), W / 2, 1120 - out * 40, 0.8 + 0.2 * eback(p), a)
    for t0, t1, s, col in [(54.5, 56.7, '24/7 ROTATION', C2), (85.8, 88.9, '10–20 YEARS OF BUSINESS', C2),
                           (112.0, 119.6, 'THE WORLD IS COMING TO AZAD', C3)]:
        if t0 <= t < t1 + 0.3:
            p = prog(t, t0, 0.4); out = prog(t, t1, 0.3)
            a = eo(p) * (1 - out)
            paste_rgba(im, sticker_img(s, col), W / 2, 1170, 0.7 + 0.3 * eback(p), a)

@functools.lru_cache(None)
def sticker_img(s, col):
    sz = 58
    while font('900', sz).getlength(s) > 820: sz -= 2
    f = font('900', sz); tw = int(f.getlength(s)); w, h = tw + 110, 140
    im = Image.new('RGBA', (w + 40, h + 40), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((26, 30, w + 26, h + 30), 34, fill=(0, 0, 0, 90))
    im = im.filter(ImageFilter.GaussianBlur(8)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((20, 20, w + 20, h + 20), 34, fill=col + (255,), outline=C5 + (255,), width=4)
    d.text((20 + w / 2, 20 + h / 2 + 2), s, font=f, fill=WHITE + (255,), anchor='mm')
    return im

@functools.lru_cache(None)
def hook_img():
    im = Image.new('RGBA', (1000, 330), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((70, 20, 930, 180), 30, fill=C1 + (235,))
    d.text((500, 102), 'CLASS 10 DROPOUT', font=font('900', 82), fill=WHITE + (255,), anchor='mm')
    d.rounded_rectangle((150, 200, 850, 300), 50, fill=C2 + (255,))
    d.text((500, 252), 'NOW SUPPLIES GLOBAL GIANTS', font=font('800', 40), fill=WHITE + (255,), anchor='mm')
    return im

# ---------------------------------------------------------------- name card
@functools.lru_cache(None)
def namecard_layers():
    w, h = 640, 190
    box = Image.new('RGBA', (w + 60, h + 60), (0, 0, 0, 0)); d = ImageDraw.Draw(box)
    d.rounded_rectangle((36, 40, w + 36, h + 40), 24, fill=(0, 0, 0, 110))
    box = box.filter(ImageFilter.GaussianBlur(10)); d = ImageDraw.Draw(box)
    d.rounded_rectangle((30, 30, w + 30, h + 30), 24, fill=WHITE + (245,))
    d.rounded_rectangle((30, 30, 52, h + 30), 10, fill=C2 + (255,))
    d.text((84, 98), 'Priyam Shah', font=font('800', 62), fill=C1 + (255,), anchor='lm')
    d.rounded_rectangle((84, 140, 84 + font('700', 30).getlength('FOUNDER') + 40, 186), 23, fill=C2 + (255,))
    d.text((104, 164), 'FOUNDER', font=font('700', 30), fill=WHITE + (255,), anchor='lm')
    return box

def namecard(im, t):
    t0, t1 = 1.0, 7.2
    if not (t0 <= t < t1 + 0.5): return
    box = namecard_layers()
    p = prog(t, t0, 0.55); out = prog(t, t1, 0.4)
    reveal = eo(p) * (1 - eio(out))
    if reveal <= 0: return
    wv = int(box.width * reveal)
    crop = box.crop((0, 0, max(1, wv), box.height))
    x = 40 - int((1 - eo(p)) * 60)
    im.paste(crop, (x, 1560), crop)
    # accent line sweeping ahead
    d = ImageDraw.Draw(im, 'RGBA')
    if reveal < 0.999:
        d.rectangle((x + wv - 6, 1590, x + wv, 1590 + 190), fill=rgba(C4, 1))

# ---------------------------------------------------------------- captions
KEY = {'class', '10', 'dropout', 'rolls-royce', 'ge', 'boeing', 'azad', 'engineering', 'rakesh', 'chopdar', '10-12',
       'factory', 'machining', 'tooling', 'cnc', 'innovated', 'complex', '3d', 'airfoils', 'airfoil', 'cold', 'hot', '24/7',
       'pressure', 'heat', '2,500', '3,000', 'celsius', 'qualification', '12', 'aerospace', 'qualified', '10-15-20',
       '₹590', '₹130', '₹6,500', 'crore', 'revenue', 'pat', 'order', 'book', 'january', '2024', 'mitsubishi', 'defence',
       'strategic', 'nozzles', 'vanes', 'world', 'sky', 'limit', '25', '30', '35%', '8', '10x', 'capacity', 'factories', 'excited'}
def kw(word):
    return re.sub(r'[.,:;!?]+$', '', word).lower() in KEY

TOK = json.load(open('aligned.json'))
def build_groups():
    groups = []; cur = []
    for i, tk in enumerate(TOK):
        cur.append(tk)
        txt = ' '.join(x['d'] for x in cur)
        nxt = TOK[i + 1] if i + 1 < len(TOK) else None
        end = (re.search(r'[.,]$', tk['d']) and len(cur) >= 2) or len(cur) >= 4 or len(txt) >= 19 or nxt is None \
            or nxt['line'] != tk['line'] or (nxt and nxt['s'] - tk['e'] > 0.6)
        if end: groups.append(cur); cur = []
    out = []
    for gi, g in enumerate(groups):
        s = g[0]['s'] - 0.08
        e = groups[gi + 1][0]['s'] - 0.08 if gi + 1 < len(groups) else MAIN_END
        e = min(e, g[-1]['e'] + 0.7)
        out.append({'s': s, 'e': e, 'w': g})
    return out
GROUPS = build_groups()
CAP_SIZE = 64

@functools.lru_cache(maxsize=4096)
def caption_img(gi, active):
    g = GROUPS[gi]['w']; f = font('800', CAP_SIZE); sp = f.getlength(' ')
    words = [re.sub(r'(?<=[a-zA-Z])[.,]$', '', x['d']) for x in g]
    widths = [f.getlength(wd) for wd in words]
    # line wrap at 900
    lines = [[]]; lw = 0
    for i, wd in enumerate(widths):
        need = wd + (sp + 24 if lines[-1] else 0)
        if lines[-1] and lw + need > 900: lines.append([]); lw = 0; need = wd
        lines[-1].append(i); lw += need
    lh = int(CAP_SIZE * 1.45)
    Wc, Hc = W, lh * len(lines) + 40
    im = Image.new('RGBA', (Wc, Hc), (0, 0, 0, 0))
    sh = Image.new('RGBA', (Wc, Hc), (0, 0, 0, 0)); ds = ImageDraw.Draw(sh)
    d = ImageDraw.Draw(im)
    pos = []
    for li, ln in enumerate(lines):
        tot = sum(widths[i] for i in ln) + (sp + 24) * (len(ln) - 1)
        x = Wc / 2 - tot / 2; y = 20 + li * lh + lh / 2
        for i in ln:
            pos.append((i, x, y)); x += widths[i] + sp + 24
    for i, x, y in pos:
        ds.text((x + 3, y + 5), words[i], font=f, fill=(0, 0, 0, 200), anchor='lm', stroke_width=6, stroke_fill=(0, 0, 0, 200))
    sh = sh.filter(ImageFilter.GaussianBlur(5))
    im.alpha_composite(sh)
    for i, x, y in pos:
        spoken = i <= active
        if kw(g[i]['d']) and spoken:
            d.rounded_rectangle((x - 12, y - CAP_SIZE * 0.62, x + widths[i] + 12, y + CAP_SIZE * 0.62), 14, fill=C2 + (255,))
            d.text((x, y), words[i], font=f, fill=WHITE + (255,), anchor='lm')
        else:
            col = C5 if i == active else WHITE
            d.text((x, y), words[i], font=f, fill=col + (255,), anchor='lm', stroke_width=5, stroke_fill=DARK + (255,))
    return im

def captions(im, t, split_p):
    for gi, g in enumerate(GROUPS):
        if g['s'] <= t < g['e']:
            act = -1
            for i, x in enumerate(g['w']):
                if t >= x['s'] - 0.04: act = i
            cap = caption_img(gi, act)
            p = prog(t, g['s'], 0.14)
            sc = 0.86 + 0.14 * eback(p)
            y = 1390 * (1 - split_p) + (PH + 6) * split_p
            paste_rgba(im, cap, W / 2, y, sc, eo(p) if p < 1 else 1)
            return

# ---------------------------------------------------------------- watermark
@functools.lru_cache(None)
def watermark():
    lg = Image.open('assets/logo_full.png').crop((78, 296, 552, 735))
    lg = lg.resize((104, int(104 * lg.height / lg.width)), Image.LANCZOS)
    # white version for contrast
    a = lg.getchannel('A').point(lambda v: int(v * 0.85))
    wim = Image.new('RGBA', lg.size, WHITE + (0,)); wim.putalpha(a)
    sh = Image.new('RGBA', (lg.width + 30, lg.height + 30), (0, 0, 0, 0))
    sa = Image.new('L', sh.size, 0); sa.paste(a.point(lambda v: int(v * 0.6)), (15, 17)); sa = sa.filter(ImageFilter.GaussianBlur(5))
    sh.putalpha(sa); sh.alpha_composite(wim, (15, 15))
    return sh

# ---------------------------------------------------------------- speaker framing
LINE_STARTS = []
_l = -1
for tk in TOK:
    if tk['line'] != _l: _l = tk['line']; LINE_STARTS.append(tk['s'] - 0.05)
def zoom_at(t):
    z = 1.0
    for i, s in enumerate(LINE_STARTS):
        target = 1.0 if i % 2 == 0 else 1.08
        if t >= s:
            z = z + (target - z) * eio(prog(t, s, 0.35))
    return z + 0.012 * math.sin(t * 0.4)

FOCUS = (540, 520)
def speaker_frame(fr, t, sp):
    z = zoom_at(t) * (1 - sp) + 1.0 * sp
    if z > 1.001:
        cw, ch = W / z, H / z
        x0 = clamp(FOCUS[0] - cw / 2 * (FOCUS[0] / (W / 2)), 0, W - cw); y0 = clamp(FOCUS[1] - ch * FOCUS[1] / H, 0, H - ch)
        fr = fr.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + cw, y0 + ch))
    return fr

def compose_main(fr, t):
    sp, fn, ft = split_state(t)
    fr = speaker_frame(fr, t, sp)
    canvas = Image.new('RGB', (W, H), (0, 0, 0))
    shift = int(eio(sp) * (PH - 230)) if sp > 0 else 0
    canvas.paste(fr, (0, shift))
    if sp > 0:
        panel = panel_base(t)
        dp = ImageDraw.Draw(panel, 'RGBA')
        fn(dp, panel, ft)
        py = int(-PH + PH * eio(sp)) + shift - int(eio(sp) * (PH - 230)) + 0
        py = int(-PH * (1 - eio(sp)))
        canvas.paste(panel, (0, py))
        d = ImageDraw.Draw(canvas, 'RGBA')
        yl = py + PH
        d.rectangle((0, yl - 3, W, yl + 3), fill=rgba(C4, 1))
        d.rectangle((0, yl + 3, W, yl + 10), fill=(0, 0, 0, 60))
    d = ImageDraw.Draw(canvas, 'RGBA')
    stickers(d, canvas, t)
    wm = watermark()
    canvas.paste(wm, (W - wm.width - 24, 40), wm)
    namecard(canvas, t)
    captions(canvas, t, eio(sp))
    # fade in from black at very start
    if t < 0.25:
        canvas = Image.blend(Image.new('RGB', (W, H)), canvas, t / 0.25)
    return canvas

# ---------------------------------------------------------------- end cards
DISC = Image.open('disclosure.png').convert('RGB')
def compose_disc(t, last_main):
    lt = t - MAIN_END
    sc = W / DISC.width
    base = DISC.resize((W, int(DISC.height * sc)), Image.LANCZOS) if not hasattr(compose_disc, 'b') else compose_disc.b
    compose_disc.b = base
    z = 1.0 + 0.03 * lt / 6
    bw, bh = int(W * z), int(base.height * z)
    im = base.resize((bw, bh), Image.BILINEAR)
    canvas = Image.new('RGB', (W, H), WHITE)
    canvas.paste(im, ((W - bw) // 2, (H - bh) // 2))
    p = eio(prog(lt, 0, 0.5))
    if p < 1 and last_main is not None:
        out = Image.new('RGB', (W, H)); out.paste(last_main, (int(-W * p), 0)); out.paste(canvas, (int(W * (1 - p)), 0))
        return out
    return canvas

END_BG = Image.open('assets/end_bg.png').convert('RGB')
END_ORIG = Image.open('endcard.png').convert('RGB')
ESC = W / END_ORIG.width
END_BG_S = END_BG.resize((W, int(END_BG.height * ESC)), Image.LANCZOS).crop((0, 0, W, H))
END_ORIG_S = END_ORIG.resize((W, int(END_ORIG.height * ESC)), Image.LANCZOS).crop((0, 0, W, H))
PIECES = {}
for k in ['wingL', 'wingR', 'armL', 'armR', 'text']:
    im = Image.open(f'assets/logo_{k}.png')
    bb = im.getchannel('A').getbbox(); pc = im.crop(bb)
    pc = pc.resize((int(pc.width * ESC), int(pc.height * ESC)), Image.LANCZOS)
    cx = (bb[0] + bb[2]) / 2 * ESC; cy = (bb[1] + bb[3]) / 2 * ESC
    PIECES[k] = (pc, cx, cy)

def compose_logo(t, last):
    lt = t - DISC_END
    canvas = END_BG_S.copy()
    anims = {'wingL': (0.35, (-220, -160)), 'wingR': (0.45, (220, -160)), 'armL': (0.6, (-260, 120)), 'armR': (0.7, (260, 120))}
    for k, (t0, (dx, dy)) in anims.items():
        pc, cx, cy = PIECES[k]
        p = prog(lt, t0, 0.65)
        if p <= 0: continue
        e = eback(p, 1.3); sc = 0.4 + 0.6 * e
        paste_rgba(canvas, pc, cx + dx * (1 - eo(p)), cy + dy * (1 - eo(p)), sc, eo(prog(lt, t0, 0.3)))
    # text wipe
    pc, cx, cy = PIECES['text']
    p = eio(prog(lt, 1.35, 0.8))
    if p > 0:
        wv = max(1, int(pc.width * p))
        crop = pc.crop((0, 0, wv, pc.height))
        a = eo(prog(lt, 1.35, 0.5))
        x = int(cx - pc.width / 2); y = int(cy - pc.height / 2 + (1 - a) * 25)
        if a < 1:
            al = crop.getchannel('A').point(lambda v: int(v * a)); crop = crop.copy(); crop.putalpha(al)
        canvas.paste(crop, (x, y), crop)
    # crossfade to exact original
    q = eio(prog(lt, 2.6, 0.6))
    if q > 0: canvas = Image.blend(canvas, END_ORIG_S, q)
    # light sweep across logo
    s = prog(lt, 2.2, 0.9)
    if 0 < s < 1:
        full = Image.open('assets/logo_full.png') if not hasattr(compose_logo, 'lf') else compose_logo.lf
        compose_logo.lf = full
        if not hasattr(compose_logo, 'mask'):
            m = full.getchannel('A').resize((W, int(full.height * ESC)), Image.LANCZOS).crop((0, 0, W, H))
            compose_logo.mask = np.asarray(m, np.float32) / 255
        yy, xx = np.mgrid[0:H, 0:W]
        band = np.exp(-(((xx + yy * 0.5) - (-300 + s * 2200)) / 70.0) ** 2) * compose_logo.mask * 0.55
        arr = np.asarray(canvas, np.float32)
        arr = arr + (255 - arr) * band[..., None]
        canvas = Image.fromarray(arr.astype(np.uint8))
    # flash transition from disclosure
    f = prog(lt, 0, 0.35)
    if f < 1 and last is not None:
        canvas = Image.blend(last, canvas, eio(f))
    return canvas

# ---------------------------------------------------------------- worker
def run(a, b, outpath):
    vf = 'scale=1080:1920:flags=lanczos,unsharp=5:5:0.7:3:3:0.0,eq=contrast=1.05:saturation=1.1:gamma=1.02,vignette=PI/6'
    dec = None
    if a < int(MAIN_END * FPS):
        n_main = min(b, int(MAIN_END * FPS)) - a
        dec = subprocess.Popen(['ffmpeg', '-v', 'error', '-ss', f'{a / FPS:.4f}', '-i', 'src.mp4', '-vf', vf + ',fps=30',
                                '-frames:v', str(n_main), '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
    enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS),
                            '-i', '-', '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-pix_fmt', 'yuv420p', outpath],
                           stdin=subprocess.PIPE)
    last_main = None; last_disc = None; prev = None
    for i in range(a, b):
        t = i / FPS
        if t < MAIN_END:
            raw = dec.stdout.read(W * H * 3)
            if len(raw) < W * H * 3:
                fr = prev if prev is not None else Image.new('RGB', (W, H))
            else:
                fr = Image.frombytes('RGB', (W, H), raw); prev = fr
            out = compose_main(fr, t)
        elif t < DISC_END:
            if last_main is None:
                last_main = compose_main(prev_or_last(), MAIN_END - 1 / FPS)
            out = compose_disc(t, last_main)
        else:
            if last_disc is None: last_disc = compose_disc(DISC_END - 1 / FPS, None)
            out = compose_logo(t, last_disc)
        enc.stdin.write(out.tobytes())
        if i % 150 == 0: print(outpath, i, flush=True)
    enc.stdin.close(); enc.wait()
    if dec: dec.stdout.close(); dec.wait()

def prev_or_last():
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-sseof', '-0.2', '-i', 'src.mp4', '-vf',
                          'scale=1080:1920:flags=lanczos,unsharp=5:5:0.7:3:3:0.0,eq=contrast=1.05:saturation=1.1:gamma=1.02,vignette=PI/6',
                          '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True).stdout
    return Image.frombytes('RGB', (W, H), raw[:W * H * 3])

if __name__ == '__main__':
    OUT = __import__('os').environ.get('OUT', 'stills')
    if sys.argv[1] == 'still':
        # render preview stills at given times
        for ts in sys.argv[2:]:
            t = float(ts)
            if t < MAIN_END:
                raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(t), '-i', 'src.mp4', '-vf',
                                      'scale=1080:1920:flags=lanczos,unsharp=5:5:0.7:3:3:0.0,eq=contrast=1.05:saturation=1.1:gamma=1.02,vignette=PI/6',
                                      '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True).stdout
                out = compose_main(Image.frombytes('RGB', (W, H), raw), t)
            elif t < DISC_END: out = compose_disc(t, None)
            else: out = compose_logo(t, None)
            out.resize((360, 640)).save(OUT+f'/s_{t:07.2f}.jpg', quality=85)
    else:
        run(int(sys.argv[1]), int(sys.argv[2]), sys.argv[3])
