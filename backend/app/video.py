"""Animated, narrated onboarding video renderer.

Pipeline: structured script -> macOS TTS per line -> audio timeline -> Pillow motion-graphics frames
(talking characters with audio-driven mouths, parallax backgrounds, animated cards, diagrams, timelines)
piped into FFmpeg -> H.264/AAC MP4.
"""
import math
import random
import shutil
import subprocess
import tempfile
import wave
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import config

SR = 22050
VOICES = {"A": "Samantha", "B": "Daniel"}
NAMES = {"A": "Sara", "B": "Ahmed"}

INK = (240, 248, 247)
MUTED = (160, 196, 196)
ACCENT = (64, 214, 190)
GOLD = (247, 196, 92)
CORAL = (240, 120, 100)
CARD = (22, 64, 72)
CARD2 = (30, 82, 92)

PALETTES = [
    ((8, 38, 48), (13, 92, 99)), ((14, 30, 58), (26, 84, 112)), ((10, 44, 52), (40, 96, 86)),
    ((20, 32, 56), (60, 70, 120)), ((8, 46, 56), (16, 110, 110)), ((24, 30, 50), (80, 60, 100)),
    ((10, 40, 40), (30, 100, 80)), ((16, 34, 60), (20, 100, 130)), ((8, 38, 48), (13, 92, 99)),
]


# ---------------------------------------------------------------- helpers
def ease(t):  # ease-out cubic
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def back(t):  # ease-out back (overshoot)
    t = max(0.0, min(1.0, t))
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


@lru_cache(maxsize=64)
def font(size: int, bold: bool = False):
    for path, idx in (("/System/Library/Fonts/Avenir Next.ttc", 2 if bold else 0),
                      ("/System/Library/Fonts/HelveticaNeue.ttc", 1 if bold else 0),
                      # Linux servers (fonts-dejavu-core)
                      (f"/usr/share/fonts/truetype/dejavu/DejaVuSans{'-Bold' if bold else ''}.ttf", 0)):
        try:
            return ImageFont.truetype(path, size, index=idx)
        except Exception:
            continue
    return ImageFont.load_default()


def wrap(draw, text, fnt, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=fnt) <= width:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def S(v):  # scale from 1280 design width
    return int(v * config.VIDEO_W / 1280)


# ---------------------------------------------------------------- audio
ESPEAK = {"Samantha": "en-us+f3", "Daniel": "en-gb+m3"}


def tts(text: str, voice: str, out: Path) -> np.ndarray:
    if shutil.which("say"):  # macOS voices (best quality)
        cmd = ["say", "-v", voice, "-r", "200", "-o", str(out), "--file-format=WAVE", f"--data-format=LEI16@{SR}", text]
    else:  # Linux servers: espeak-ng, resampled to our rate by ffmpeg
        raw = out.with_suffix(".raw.wav")
        subprocess.run(["espeak-ng", "-v", ESPEAK.get(voice, "en-us"), "-s", "165", "-w", str(raw), text], check=True, capture_output=True, timeout=60)
        cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-ar", str(SR), "-ac", "1", "-sample_fmt", "s16", str(out)]
    for attempt in range(3):  # the macOS speech service occasionally stalls; retry instead of failing the stage
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=30)
            break
        except subprocess.TimeoutExpired:
            if attempt == 2:
                raise
    with wave.open(str(out)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)


def build_audio(scenes, tmp: Path):
    """Returns (pcm int16, timeline). timeline: per scene {start,end,lines:[{start,end,speaker,text}]}."""
    chunks, timeline, t = [], [], 0.0

    def silence(sec):
        nonlocal t
        chunks.append(np.zeros(int(sec * SR), dtype=np.int16))
        t += sec

    for si, sc in enumerate(scenes):
        s_start = t
        silence(0.45)
        lines = []
        for li, ln in enumerate(sc["lines"]):
            pcm = tts(ln["text"], VOICES.get(ln["speaker"], "Samantha"), tmp / f"s{si}_{li}.wav")
            lines.append({"start": t, "end": t + len(pcm) / SR, "speaker": ln["speaker"], "text": ln["text"]})
            chunks.append(pcm)
            t += len(pcm) / SR
            silence(0.2)
        silence(0.4)
        timeline.append({"start": s_start, "end": t, "lines": lines})
    return np.concatenate(chunks), timeline


def envelope(pcm: np.ndarray, fps: int) -> np.ndarray:
    hop = SR // fps
    n = len(pcm) // hop + 1
    padded = np.zeros(n * hop, dtype=np.float32)
    padded[: len(pcm)] = pcm.astype(np.float32) / 32768
    rms = np.sqrt((padded.reshape(n, hop) ** 2).mean(axis=1))
    return np.clip(rms / 0.12, 0, 1)


# ---------------------------------------------------------------- scenery
class Backdrop:
    def __init__(self, idx, seed):
        W, H = config.VIDEO_W, config.VIDEO_H
        top, bot = PALETTES[idx % len(PALETTES)]
        grad = np.linspace(0, 1, H)[:, None, None]
        arr = (np.array(top)[None, None, :] * (1 - grad) + np.array(bot)[None, None, :] * grad)
        arr = np.repeat(arr, W, axis=1).astype(np.uint8)
        self.base = Image.fromarray(arr, "RGB")
        rnd = random.Random(seed)
        self.blobs = []
        for _ in range(5):
            r = rnd.randint(S(120), S(260))
            col = rnd.choice([ACCENT, GOLD, (90, 140, 255), CORAL])
            b = r // 3
            spr = Image.new("L", (r * 2 + b * 4, r * 2 + b * 4), 0)  # margin so the blur never reaches the edge
            ImageDraw.Draw(spr).ellipse((b * 2, b * 2, b * 2 + r * 2, b * 2 + r * 2), fill=rnd.randint(28, 52))
            spr = spr.filter(ImageFilter.GaussianBlur(b))
            self.blobs.append(dict(spr=spr, col=Image.new("RGB", spr.size, col), x=rnd.uniform(0, W), y=rnd.uniform(0, H * 0.7),
                                   vx=rnd.uniform(-22, 22), vy=rnd.uniform(-10, 10), ph=rnd.uniform(0, 6.28), depth=rnd.uniform(0.4, 1.2)))
        self.dots = [(rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(1, 3), rnd.uniform(0.3, 1.0)) for _ in range(40)]

    def render(self, t):
        W, H = config.VIDEO_W, config.VIDEO_H
        img = self.base.copy()
        for b in self.blobs:
            x = (b["x"] + b["vx"] * t * b["depth"] + 40 * math.sin(t * 0.5 + b["ph"])) % (W + 300) - 150
            y = b["y"] + b["vy"] * t + 30 * math.cos(t * 0.4 + b["ph"])
            img.paste(b["col"], (int(x - b["spr"].width / 2), int(y - b["spr"].height / 2)), b["spr"])
        d = ImageDraw.Draw(img)
        for x, y, r, sp in self.dots:  # drifting particles (parallax layer)
            yy = (y - t * 18 * sp) % H
            xx = (x + math.sin(t * sp + x) * 12) % W
            d.ellipse((xx - r, yy - r, xx + r, yy + r), fill=lerp(INK, (40, 90, 100), 0.6))
        return img, d


# ---------------------------------------------------------------- characters
SKIN = {"A": (224, 178, 140), "B": (196, 146, 108)}
SHIRT = {"A": (64, 214, 190), "B": (247, 196, 92)}


def draw_person(d, cx, base_y, who, talk, t, active):
    k = config.VIDEO_W / 1280 * 0.62
    bob = math.sin(t * 2.2 + (0 if who == "A" else 1.5)) * 3 * k + (talk * 3 * k if active else 0)
    lean = math.sin(t * 1.3 + (0 if who == "A" else 2)) * 4 * k
    hy = base_y - 150 * k + bob
    hx = cx + lean
    skin, shirt = SKIN[who], SHIRT[who]
    # glow ring when speaking
    if active:
        rr = (78 + 8 * talk) * k
        d.ellipse((hx - rr, hy - rr + 20 * k, hx + rr, hy + rr + 20 * k), outline=lerp(shirt, INK, 0.3), width=max(2, int(3 * k)))
    # torso
    d.rounded_rectangle((cx - 62 * k, base_y - 92 * k + bob * 0.5, cx + 62 * k, base_y + 40 * k), radius=int(46 * k), fill=shirt)
    d.polygon([(cx - 14 * k, base_y - 92 * k + bob * 0.5), (cx + 14 * k, base_y - 92 * k + bob * 0.5), (cx, base_y - 66 * k + bob * 0.5)], fill=lerp(shirt, (255, 255, 255), 0.5))
    # gesturing arm when speaking
    ang = (math.sin(t * 5) * 0.35 + 0.6) if active and talk > 0.15 else 0.15
    sx, sy = cx + (52 if who == "A" else -52) * k, base_y - 70 * k + bob * 0.5
    dirx = 1 if who == "A" else -1
    ex, ey = sx + dirx * math.cos(ang) * 52 * k, sy - math.sin(ang) * 52 * k
    d.line((sx, sy, ex, ey), fill=lerp(shirt, (0, 0, 0), 0.15), width=int(20 * k))
    d.ellipse((ex - 11 * k, ey - 11 * k, ex + 11 * k, ey + 11 * k), fill=skin)
    # neck + head
    d.rectangle((hx - 12 * k, hy + 30 * k, hx + 12 * k, hy + 60 * k), fill=lerp(skin, (0, 0, 0), 0.1))
    if who == "A":  # headscarf
        d.ellipse((hx - 50 * k, hy - 52 * k, hx + 50 * k, hy + 58 * k), fill=(40, 70, 120))
        d.polygon([(hx - 48 * k, hy + 10 * k), (hx + 48 * k, hy + 10 * k), (hx + 30 * k, hy + 75 * k), (hx - 30 * k, hy + 75 * k)], fill=(40, 70, 120))
        d.ellipse((hx - 36 * k, hy - 36 * k, hx + 36 * k, hy + 42 * k), fill=skin)
    else:
        d.ellipse((hx - 40 * k, hy - 42 * k, hx + 40 * k, hy + 44 * k), fill=skin)
        d.chord((hx - 42 * k, hy - 46 * k, hx + 42 * k, hy + 20 * k), 180, 360, fill=(40, 32, 28))
        d.chord((hx - 34 * k, hy + 8 * k, hx + 34 * k, hy + 50 * k), 0, 180, fill=(52, 42, 36))  # beard
    # eyes with blink
    blink = (t * 0.9 + (0.3 if who == "B" else 0)) % 3.7 < 0.12
    eh = 1.5 * k if blink else 6 * k
    for ox in (-14, 14):
        d.ellipse((hx + ox * k - 5 * k, hy - 4 * k - eh, hx + ox * k + 5 * k, hy - 4 * k + eh), fill=(30, 30, 40))
    # mouth driven by audio envelope
    my = hy + 20 * k
    if active and talk > 0.05:
        oh = (3 + 13 * talk) * k
        d.ellipse((hx - 11 * k, my - oh / 2, hx + 11 * k, my + oh / 2), fill=(110, 40, 50))
    else:
        d.arc((hx - 12 * k, my - 8 * k, hx + 12 * k, my + 6 * k), 20, 160, fill=(110, 50, 50), width=max(2, int(3 * k)))
    # name tag
    f = font(S(14), True)
    label = NAMES[who]
    tw = d.textlength(label, font=f)
    d.rounded_rectangle((cx - tw / 2 - 10 * k, base_y + 46 * k, cx + tw / 2 + 10 * k, base_y + 70 * k), radius=int(12 * k), fill=(0, 0, 0) if active else (20, 50, 56))
    d.text((cx - tw / 2, base_y + 48 * k), label, font=f, fill=shirt if active else MUTED)


# ---------------------------------------------------------------- scene drawing primitives
def title(d, text, lt, y=S(54), x=S(70), size=44, sub=None):
    p = ease(lt / 0.7)
    f = font(S(size), True)
    d.text((x - (1 - p) * S(60), y), text, font=f, fill=lerp(CARD, INK, p))
    w = d.textlength(text, font=f)
    d.rounded_rectangle((x, y + S(size) + S(16), x + w * ease((lt - 0.2) / 0.8), y + S(size) + S(22)), radius=S(3), fill=ACCENT)
    if sub:
        ps = ease((lt - 0.35) / 0.6)
        d.text((x, y + S(size) + S(34) + (1 - ps) * S(20)), sub, font=font(S(22)), fill=lerp(CARD, MUTED, ps))


def card(d, box, lt, delay, heading=None, body=None, accent=ACCENT, from_dir=(0, 1), body_size=18, head_size=22, width_chars=None):
    p = back((lt - delay) / 0.6)
    if lt < delay:
        return
    fade = ease((lt - delay) / 0.45)
    x0, y0, x1, y1 = box
    dx, dy = (1 - p) * S(80) * from_dir[0], (1 - p) * S(80) * from_dir[1]
    bx = (x0 + dx, y0 + dy, x1 + dx, y1 + dy)
    d.rounded_rectangle(bx, radius=S(18), fill=lerp(PALETTES[0][0], CARD, fade))
    d.rounded_rectangle((bx[0], bx[1], bx[0] + S(6), bx[3]), radius=S(3), fill=lerp(CARD, accent, fade))
    ty = bx[1] + S(16)
    if heading:
        for ln in wrap(d, heading, font(S(head_size), True), (x1 - x0) - S(40))[:2]:
            d.text((bx[0] + S(24), ty), ln, font=font(S(head_size), True), fill=lerp(CARD, INK, fade))
            ty += S(head_size + 6)
    if body:
        ty += S(4)
        for ln in wrap(d, body, font(S(body_size)), (x1 - x0) - S(44))[:5]:
            d.text((bx[0] + S(24), ty), ln, font=font(S(body_size)), fill=lerp(CARD, MUTED, fade))
            ty += S(body_size + 7)


def badge(d, x, y, text, col, lt, delay):
    if lt < delay:
        return 0
    p = back((lt - delay) / 0.4)
    f = font(S(15), True)
    w = d.textlength(text, font=f) + S(22)
    h = S(28)
    cx, cy = x + w / 2, y + h / 2
    d.rounded_rectangle((cx - w / 2 * p, cy - h / 2 * p, cx + w / 2 * p, cy + h / 2 * p), radius=S(14), fill=col)
    if p > 0.8:
        d.text((x + S(11), y + S(4)), text, font=f, fill=(10, 30, 34))
    return w


def node(d, cx, cy, r, label, col, lt, delay, sub=None):
    if lt < delay:
        return
    p = back((lt - delay) / 0.5)
    pulse = 1 + 0.04 * math.sin(lt * 3 + cx)
    rr = r * p * pulse
    d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), fill=col)
    d.ellipse((cx - rr - S(6), cy - rr - S(6), cx + rr + S(6), cy + rr + S(6)), outline=lerp(col, INK, 0.3), width=S(2))
    if p > 0.7:
        f = font(S(17), True)
        lines = wrap(d, label, f, r * 1.75)[:3]
        yy = cy - len(lines) * S(11)
        for ln in lines:
            d.text((cx - d.textlength(ln, font=f) / 2, yy), ln, font=f, fill=(10, 30, 34))
            yy += S(22)
        if sub:
            fs = font(S(15))
            for i, ln in enumerate(wrap(d, sub, fs, r * 2.6)[:2]):
                d.text((cx - d.textlength(ln, font=fs) / 2, cy + rr + S(12) + i * S(19)), ln, font=fs, fill=MUTED)


def connector(d, a, b, lt, delay, dur=0.6, col=ACCENT, flow=True):
    if lt < delay:
        return
    p = ease((lt - delay) / dur)
    x = a[0] + (b[0] - a[0]) * p
    y = a[1] + (b[1] - a[1]) * p
    d.line((a[0], a[1], x, y), fill=lerp(col, (0, 0, 0), 0.35), width=S(4))
    if flow and p >= 1:  # packets travelling along the link
        for k in range(2):
            q = ((lt * 0.6 + k * 0.5) % 1)
            px, py = a[0] + (b[0] - a[0]) * q, a[1] + (b[1] - a[1]) * q
            d.ellipse((px - S(5), py - S(5), px + S(5), py + S(5)), fill=col)


def mini_face(d, cx, cy, r, col, lt):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=col)
    d.ellipse((cx - r * 0.55, cy - r * 0.6, cx + r * 0.55, cy + r * 0.45), fill=(224, 178, 140))
    blink = (lt + cx) % 3 < 0.1
    for ox in (-0.2, 0.2):
        d.ellipse((cx + ox * r - 2, cy - r * 0.2 - (1 if blink else 3), cx + ox * r + 2, cy - r * 0.2 + (1 if blink else 3)), fill=(30, 30, 40))
    d.arc((cx - r * 0.22, cy - r * 0.05, cx + r * 0.22, cy + r * 0.22), 20, 160, fill=(110, 50, 50), width=2)


# ---------------------------------------------------------------- scene renderers (content area: y 40..560)
W0 = 1280


def sc_welcome(d, lt, dur, v):
    W = config.VIDEO_W
    f = font(S(30), True)
    d.text((S(70), S(70)), v["company"].upper(), font=font(S(18), True), fill=lerp(CARD, ACCENT, ease(lt / 0.6)))
    word = f"Welcome, {v['first']}!"
    fb = font(S(78), True)
    x = S(70)
    for i, ch in enumerate(word):  # staggered letter pop
        p = back((lt - 0.2 - i * 0.04) / 0.45)
        if lt < 0.2 + i * 0.04:
            break
        d.text((x, S(150) + (1 - p) * S(50)), ch, font=fb, fill=lerp(CARD, INK, min(1, p)))
        x += d.textlength(ch, font=fb)
    badge(d, S(72), S(270), v["title"], ACCENT, lt, 1.2)
    badge(d, S(72) + S(20) + d.textlength(v["title"], font=font(S(15), True)) + S(22), S(270), v["dept"], GOLD, lt, 1.4)
    d.text((S(72), S(330)), "Your first days, explained.", font=font(S(24)), fill=lerp(CARD, MUTED, ease((lt - 1.6) / 0.6)))
    # orbiting logo mark
    cx, cy = W - S(260), S(230)
    for i in range(3):
        a = lt * (0.8 + i * 0.3) + i * 2.1
        r = S(70 + i * 38)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=lerp(CARD, ACCENT, 0.3 + i * 0.15), width=S(2))
        px, py = cx + math.cos(a) * r, cy + math.sin(a) * r
        d.ellipse((px - S(9), py - S(9), px + S(9), py + S(9)), fill=[ACCENT, GOLD, CORAL][i])
    p = back((lt - 0.3) / 0.6)
    d.regular_polygon((cx, cy, S(46) * p), 6, rotation=lt * 20, fill=ACCENT)


def sc_company(d, lt, dur, v):
    title(d, "Who we are", lt, sub=v["company"])
    stats = v["stats"]
    for i, (num, label) in enumerate(stats):
        x0 = S(70) + i * S(290)
        card(d, (x0, S(190), x0 + S(260), S(320)), lt, 0.5 + i * 0.25, None, None, accent=[ACCENT, GOLD, CORAL, (120, 160, 255)][i % 4])
        if lt > 0.7 + i * 0.25:
            p = ease((lt - 0.7 - i * 0.25) / 1.0)
            n = num if not str(num).isdigit() else str(int(int(num) * p))
            d.text((x0 + S(26), S(205)), n, font=font(S(48), True), fill=INK)
            d.text((x0 + S(26), S(268)), label, font=font(S(18)), fill=MUTED)
    for i, pr in enumerate(v["priorities"][:3]):
        dl = 1.8 + i * 0.4
        if lt > dl:
            p = ease((lt - dl) / 0.5)
            y = S(350) + i * S(54)
            d.ellipse((S(74), y + S(8), S(94), y + S(28)), fill=GOLD)
            d.text((S(110) - (1 - p) * S(40), y), pr, font=font(S(24)), fill=lerp(CARD, INK, p))


def sc_department(d, lt, dur, v):
    title(d, v["dept"], lt, sub="Your department")
    cx, cy = S(900), S(320)
    node(d, cx, cy, S(78), v["dept_short"], ACCENT, lt, 0.4)
    others = v["other_depts"][:4]
    for i, o in enumerate(others):
        a = -math.pi / 2 + i * (2 * math.pi / max(1, len(others))) + lt * 0.15
        ox, oy = cx + math.cos(a) * S(195), cy + math.sin(a) * S(165)
        connector(d, (cx, cy), (ox, oy), lt, 0.8 + i * 0.2)
        node(d, ox, oy, S(50), o, lerp(CARD2, INK, 0.75), lt, 1.0 + i * 0.2)
    card(d, (S(70), S(200), S(620), S(420)), lt, 0.7, "Our mission", v["mission"], from_dir=(-1, 0))
    card(d, (S(70), S(440), S(620), S(540)), lt, 1.6, f"You: {v['title']}", v["role_summary"], accent=GOLD, from_dir=(-1, 0), body_size=16)


def sc_team(d, lt, dur, v):
    title(d, "Your team", lt, sub="The people you'll work with")
    cx, cy = S(640), S(345)
    people = v["people"][:5]
    pos = [(S(250), S(230)), (S(1030), S(230)), (S(250), S(470)), (S(1030), S(470)), (S(640), S(520))]
    for i, ppl in enumerate(people):
        px, py = pos[i]
        connector(d, (cx, cy), (px, py), lt, 0.6 + i * 0.35, col=[GOLD, ACCENT, CORAL, (120, 160, 255), ACCENT][i])
    p = back((lt - 0.3) / 0.5)
    if lt > 0.3:
        d.ellipse((cx - S(62) * p, cy - S(62) * p, cx + S(62) * p, cy + S(62) * p), fill=GOLD)
        mini_face(d, cx, cy - S(4), S(40) * p, (40, 70, 120), lt)
        f = font(S(18), True)
        d.text((cx - d.textlength(v["first"], font=f) / 2, cy + S(68)), v["first"] + " (you)", font=f, fill=INK)
    for i, ppl in enumerate(people):
        px, py = pos[i]
        dl = 0.9 + i * 0.35
        if lt < dl:
            continue
        pp = back((lt - dl) / 0.5)
        w, h = S(300), S(84)
        x0, y0 = px - w / 2, py - h / 2 + (1 - pp) * S(40)
        d.rounded_rectangle((x0, y0, x0 + w, y0 + h), radius=S(16), fill=CARD)
        col = [GOLD, ACCENT, CORAL, (120, 160, 255), ACCENT][i]
        mini_face(d, x0 + S(44), y0 + h / 2, S(28), col, lt)
        d.text((x0 + S(84), y0 + S(12)), ppl["name"], font=font(S(19), True), fill=INK)
        d.text((x0 + S(84), y0 + S(38)), ppl["tag"], font=font(S(14), True), fill=col)
        d.text((x0 + S(84), y0 + S(58)), ppl["title"][:32], font=font(S(13)), fill=MUTED)


def sc_project(d, lt, dur, v):
    pj = v["project"]
    title(d, pj["name"], lt, size=36, sub=f"Client: {pj['client']}  ·  Phase: {pj['phase']}")
    card(d, (S(70), S(185), S(560), S(400)), lt, 0.6, "Background", pj["background"], from_dir=(-1, 0), body_size=17)
    # objectives path with a moving dot
    objs = pj["objectives"][:3]
    xs = [S(680) + i * S(200) for i in range(len(objs))]
    y = S(270)
    for i in range(len(objs) - 1):
        connector(d, (xs[i], y), (xs[i + 1], y), lt, 1.0 + i * 0.4, col=GOLD)
    for i, o in enumerate(objs):
        node(d, xs[i], y, S(44), f"Goal {i + 1}", GOLD if i % 2 == 0 else ACCENT, lt, 0.8 + i * 0.4, sub=o)
    # deliverables chips
    xx = S(70)
    if lt > 2.0:
        d.text((S(70), S(430)), "Key deliverables", font=font(S(20), True), fill=INK)
    for i, dl in enumerate(pj["deliverables"][:4]):
        w = badge(d, xx, S(468), dl, [ACCENT, GOLD, CORAL, (140, 180, 255)][i], lt, 2.2 + i * 0.25)
        xx += (w or 0) + S(12)


def sc_resp(d, lt, dur, v):
    title(d, "What you'll be doing", lt, sub="Your first responsibilities and the support you'll get")
    colors = {"independent": ACCENT, "light-guidance": GOLD, "mentoring": CORAL}
    labels = {"independent": "On your own", "light-guidance": "Light guidance", "mentoring": "With a mentor"}
    for i, r in enumerate(v["responsibilities"][:5]):
        dl = 0.6 + i * 0.45
        if lt < dl:
            continue
        p = ease((lt - dl) / 0.5)
        y = S(190) + i * S(70)
        x = S(70) + (1 - p) * S(-120)
        d.rounded_rectangle((x, y, x + S(1140), y + S(58)), radius=S(14), fill=lerp(PALETTES[5][0], CARD, p))
        # animated check-circle
        cp = ease((lt - dl - 0.3) / 0.4)
        d.ellipse((x + S(16), y + S(13), x + S(48), y + S(45)), outline=colors[r["level"]], width=S(3))
        if cp > 0:
            d.line((x + S(23), y + S(29), x + S(23) + S(7) * cp, y + S(29) + S(7) * cp), fill=colors[r["level"]], width=S(4))
            if cp > 0.5:
                d.line((x + S(30), y + S(36), x + S(30) + S(12) * (cp - 0.5) * 2, y + S(36) - S(14) * (cp - 0.5) * 2), fill=colors[r["level"]], width=S(4))
        d.text((x + S(66), y + S(14)), r["title"], font=font(S(22), True), fill=lerp(CARD, INK, p))
        badge(d, x + S(940), y + S(15), labels[r["level"]], colors[r["level"]], lt, dl + 0.4)


def sc_example(d, lt, dur, v):
    ex = v["example"]
    title(d, "A real example of your work", lt, size=38, sub=ex["title"])
    card(d, (S(70), S(190), S(520), S(420)), lt, 0.5, "The situation", ex["scenario"], accent=CORAL, from_dir=(-1, 0), body_size=17)
    steps = ex["steps"][:5]
    span = max(1.0, (dur - 3.0) / max(1, len(steps)))
    for i, st in enumerate(steps):
        dl = 1.2 + i * span
        if lt < dl:
            continue
        p = ease((lt - dl) / 0.5)
        y = S(190) + i * S(64)
        x = S(580)
        active = lt < dl + span
        d.rounded_rectangle((x + (1 - p) * S(80), y, S(1210), y + S(54)), radius=S(14), fill=CARD2 if active else CARD)
        d.ellipse((x + S(14), y + S(11), x + S(46), y + S(43)), fill=GOLD if active else ACCENT)
        d.text((x + S(24), y + S(13)), str(i + 1), font=font(S(18), True), fill=(10, 30, 34))
        for j, ln in enumerate(wrap(d, st, font(S(17)), S(540))[:2]):
            d.text((x + S(62) + (1 - p) * S(80), y + S(6) + j * S(22) + (S(10) if len(wrap(d, st, font(S(17)), S(540))) == 1 else 0)), ln, font=font(S(17)), fill=INK)
        if active:  # pointer cursor moving along the step
            px = x + S(80) + (S(500)) * ((lt - dl) / span)
            d.polygon([(px, y + S(30)), (px + S(14), y + S(44)), (px + S(5), y + S(44))], fill=INK)
    if lt > dur - 2.5:
        p = ease((lt - (dur - 2.5)) / 0.6)
        d.rounded_rectangle((S(70), S(440), S(520), S(530)), radius=S(16), fill=lerp(CARD, (30, 90, 70), p))
        d.text((S(92), S(452)), "Deliverable", font=font(S(16), True), fill=ACCENT)
        for j, ln in enumerate(wrap(d, ex["deliverable"], font(S(16)), S(400))[:2]):
            d.text((S(92), S(476) + j * S(21)), ln, font=font(S(16)), fill=INK)


def sc_learning(d, lt, dur, v):
    title(d, "Your learning path", lt, sub="Tailored to your experience")
    courses = v["courses"][:5]
    y = S(330)
    x0, x1 = S(110), S(1170)
    pr = ease((lt - 0.5) / max(1.0, dur - 2.0))
    d.line((x0, y, x1, y), fill=CARD2, width=S(8))
    d.line((x0, y, x0 + (x1 - x0) * pr, y), fill=ACCENT, width=S(8))
    n = max(1, len(courses))
    for i, c in enumerate(courses):
        cx = x0 + (x1 - x0) * (i + 0.5) / n
        reached = pr >= (i + 0.5) / n
        col = {"mandatory": CORAL, "high": GOLD, "recommended": ACCENT, "optional": (140, 180, 255)}[c["priority"]]
        rr = S(18) * (1.25 if reached else 1)
        d.ellipse((cx - rr, y - rr, cx + rr, y + rr), fill=col if reached else CARD)
        if reached:
            up = i % 2 == 0
            bw = S(220)
            by0 = y - S(170) if up else y + S(40)
            p = back(min(1, (pr - (i + 0.5) / n) * n * 2))
            d.rounded_rectangle((cx - bw / 2, by0 + (1 - p) * S(20), cx + bw / 2, by0 + S(130) + (1 - p) * S(20)), radius=S(14), fill=CARD)
            d.text((cx - bw / 2 + S(14), by0 + S(10)), c["priority"].upper(), font=font(S(13), True), fill=col)
            for j, ln in enumerate(wrap(d, c["title"], font(S(16), True), bw - S(28))[:3]):
                d.text((cx - bw / 2 + S(14), by0 + S(32) + j * S(21)), ln, font=font(S(16), True), fill=INK)
            d.text((cx - bw / 2 + S(14), by0 + S(102)), (f"{c['hours']:g} h · " if c["hours"] else "") + c.get("provider", "")[:24], font=font(S(14)), fill=MUTED)
    # traveller dot
    tx = x0 + (x1 - x0) * pr
    d.ellipse((tx - S(12), y - S(12), tx + S(12), y + S(12)), fill=INK)


def sc_next(d, lt, dur, v, rnd=random.Random(7)):
    title(d, "Your next steps", lt, sub="Everything is waiting on your dashboard")
    for i, s in enumerate(v["next"][:4]):
        dl = 0.6 + i * 0.5
        if lt < dl:
            continue
        p = back((lt - dl) / 0.5)
        y = S(195) + i * S(70)
        d.rounded_rectangle((S(70), y, S(70) + S(640) * min(1, p), y + S(56)), radius=S(14), fill=CARD)
        if p > 0.8:
            d.text((S(96), y + S(14)), f"{i + 1}.  {s}", font=font(S(21), True), fill=INK)
    if lt > dur - 3.5:  # confetti burst
        k = lt - (dur - 3.5)
        for i in range(60):
            r = random.Random(i)
            x = S(900) + math.cos(r.uniform(0, 6.28)) * k * r.uniform(60, 260) * config.VIDEO_W / 1280
            y = S(260) + math.sin(r.uniform(0, 6.28)) * k * r.uniform(40, 200) + k * k * 40
            c = r.choice([ACCENT, GOLD, CORAL, INK])
            d.rectangle((x, y, x + S(8), y + S(5)), fill=c)
    p = back((lt - 1.0) / 0.7)
    if lt > 1.0:
        f = font(S(40), True)
        txt = f"Welcome aboard, {v['first']}!"
        d.text((S(900) - d.textlength(txt, font=f) / 2, S(240) + (1 - p) * S(40)), txt, font=f, fill=GOLD)


def sc_background(d, lt, dur, v):
    title(d, f"Your background, {v['first']}", lt, sub="What we learned from your CV")
    chips = v.get("background_chips") or []
    icons = ["🎓", "💼", "🏆"]
    labels = ["Education", "Experience", "Highlight"]
    for i, c in enumerate(chips):
        dl = 0.6 + i * 0.7
        if lt < dl:
            continue
        p = back((lt - dl) / 0.5)
        y = S(195) + i * S(110)
        x = S(70) + (1 - p) * S(-140)
        d.rounded_rectangle((x, y, x + S(760), y + S(90)), radius=S(18), fill=CARD)
        col = [ACCENT, GOLD, CORAL][i % 3]
        d.ellipse((x + S(20), y + S(18), x + S(74), y + S(72)), fill=col)
        d.text((x + S(34), y + S(30)), labels[i][0], font=font(S(24), True), fill=(10, 30, 34))
        d.text((x + S(96), y + S(14)), labels[i].upper(), font=font(S(14), True), fill=col)
        for j, ln in enumerate(wrap(d, c, font(S(22), True), S(640))[:2]):
            d.text((x + S(96), y + S(36) + j * S(26)), ln, font=font(S(22), True), fill=INK)
    # orbiting "CV" document on the right
    cx, cy = S(1030), S(330)
    a = lt * 0.8
    p = back((lt - 0.3) / 0.6)
    if lt > 0.3:
        w, h = S(150) * p, S(190) * p
        d.rounded_rectangle((cx - w / 2, cy - h / 2 + math.sin(a) * S(8), cx + w / 2, cy + h / 2 + math.sin(a) * S(8)), radius=S(12), fill=INK)
        for k in range(6):
            ly = cy - h / 2 + S(30) + k * S(24) + math.sin(a) * S(8)
            lw = (S(100) if k % 3 else S(60)) * ease((lt - 0.6 - k * 0.15) / 0.4)
            if lw > 0:
                d.rounded_rectangle((cx - S(55), ly, cx - S(55) + lw, ly + S(8)), radius=S(4), fill=[ACCENT, GOLD, CORAL][k % 3])
        # scanning line
        sy = cy - h / 2 + (h * ((lt * 0.5) % 1))
        d.line((cx - w / 2 - S(10), sy, cx + w / 2 + S(10), sy), fill=ACCENT, width=S(3))


RENDERERS = {"background": sc_background, "welcome": sc_welcome, "company": sc_company, "department": sc_department, "team": sc_team, "project": sc_project,
             "responsibilities": sc_resp, "example": sc_example, "learning": sc_learning, "next": sc_next}


def caption(d, text, lt):
    W, H = config.VIDEO_W, config.VIDEO_H
    f = font(S(21))
    lines = wrap(d, text, f, S(740))[-3:]
    x0, x1 = S(250), S(1030)
    h = S(22 + 28 * len(lines))
    y0 = H - S(20) - h
    d.rounded_rectangle((x0, y0, x1, y0 + h), radius=S(16), fill=(6, 20, 26))
    for i, ln in enumerate(lines):
        d.text(((x0 + x1) / 2 - d.textlength(ln, font=f) / 2, y0 + S(11) + i * S(28)), ln, font=f, fill=INK)


# ---------------------------------------------------------------- main entry
def render(script: dict, out_path: Path) -> dict:
    if not shutil.which("ffmpeg") or not (shutil.which("say") or shutil.which("espeak-ng")):
        raise RuntimeError("ffmpeg and a text-to-speech engine (macOS 'say' or espeak-ng) are required for video rendering")
    fps, W, H = config.VIDEO_FPS, config.VIDEO_W, config.VIDEO_H
    scenes = script["scenes"]
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        pcm, timeline = build_audio(scenes, tmp)
        wav = tmp / "audio.wav"
        with wave.open(str(wav), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
        env = envelope(pcm, fps)
        total = len(pcm) / SR
        nframes = int(total * fps)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_out = out_path.with_suffix(".part.mp4")
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
               "-i", str(wav), "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", str(tmp_out)]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        backdrops = [Backdrop(i, i * 13 + 5) for i in range(len(scenes))]
        si = 0
        try:
            for fi in range(nframes):
                t = fi / fps
                while si < len(timeline) - 1 and t >= timeline[si]["end"]:
                    si += 1
                sc, tl = scenes[si], timeline[si]
                lt, dur = t - tl["start"], tl["end"] - tl["start"]
                img, d = backdrops[si].render(t)
                RENDERERS[sc["key"]](d, lt, dur, sc["visual"])
                cur = next((l for l in tl["lines"] if l["start"] - 0.05 <= t <= l["end"] + 0.25), None)
                talk = float(env[min(fi, len(env) - 1)])
                draw_person(d, S(110), H - S(48), "A", talk, t, bool(cur and cur["speaker"] == "A"))
                draw_person(d, W - S(110), H - S(48), "B", talk, t, bool(cur and cur["speaker"] == "B"))
                if cur:
                    caption(d, cur["text"], lt)
                if lt < 0.45 and si > 0:  # wipe transition
                    p = ease(lt / 0.45)
                    if W * p < W:
                        d.rectangle((W * p, 0, W, H), fill=ACCENT)
                    if W * p + S(30) < W:
                        d.rectangle((W * p + S(30), 0, W, H), fill=PALETTES[si % len(PALETTES)][0])
                # progress bar across the top
                d.rectangle((0, 0, W * t / total, S(5)), fill=ACCENT)
                proc.stdin.write(img.tobytes())
            proc.stdin.close()
            err = proc.stderr.read().decode()
            if proc.wait() != 0:
                raise RuntimeError(f"ffmpeg failed: {err[-400:]}")
        except Exception:
            proc.kill()
            tmp_out.unlink(missing_ok=True)
            raise
        tmp_out.replace(out_path)
    return {"duration": round(total, 1), "frames": nframes, "fps": fps, "size": f"{W}x{H}", "scenes": len(scenes)}


def probe(path: Path) -> dict:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name:format=duration", "-of", "json", str(path)],
                       capture_output=True, text=True)
    import json
    return json.loads(r.stdout)
