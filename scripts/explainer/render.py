"""Tamheed explainer: a ~2-minute, music-only, presentation-style motion-graphics video of how the system works.
Usage: .venv/bin/python scripts/explainer/render.py OUT.mp4 [--frames t1,t2,...]  (frames mode writes PNG stills)"""
import math
import random
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pygments import lex
from pygments.lexers import PythonLexer
from pygments.token import Comment, Keyword, Name, Number, Operator, String

W, H, FPS = 1920, 1080, 30
ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data" / "explainer"

BG1, BG2 = (5, 30, 35), (12, 78, 86)
INK, MUTED, DIM = (240, 248, 247), (150, 190, 190), (70, 110, 115)
TEAL, GOLD, CORAL, BLUE = (64, 214, 190), (247, 196, 92), (240, 120, 100), (120, 165, 255)
CARD, CARD2, LINE = (14, 58, 66), (20, 74, 83), (35, 95, 104)
WHITE, PAPER, PINK = (255, 255, 255), (245, 248, 248), (251, 233, 230)


# ---------------------------------------------------------------- helpers
def ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def inout(t):
    t = max(0.0, min(1.0, t))
    return 3 * t * t - 2 * t * t * t


def back(t):
    t = max(0.0, min(1.0, t))
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def lerp(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


@lru_cache(maxsize=128)
def font(size, bold=False, heavy=False):
    idx = 8 if heavy else (2 if bold else 0)  # Avenir Next: 0 regular, 2 demi-bold, 8 heavy
    for path, i in (("/System/Library/Fonts/Avenir Next.ttc", idx), ("/System/Library/Fonts/HelveticaNeue.ttc", 1 if bold else 0)):
        try:
            return ImageFont.truetype(path, size, index=i)
        except Exception:
            continue
    return ImageFont.load_default()


@lru_cache(maxsize=16)
def mono(size, bold=False):
    return ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", size, index=1 if bold else 0)


def wrap(d, text, f, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= width:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def text_in(d, xy, txt, f, col, lt, delay, dur=0.6, dy=24, bg=BG1):
    """Text that slides up and fades in from the background colour."""
    if lt < delay:
        return
    p = ease((lt - delay) / dur)
    d.text((xy[0], xy[1] + (1 - p) * dy), txt, font=f, fill=lerp(bg, col, p))


def ctext(d, cx, y, txt, f, col):
    d.text((cx - d.textlength(txt, font=f) / 2, y), txt, font=f, fill=col)


def rrect(d, box, r, fill=None, outline=None, width=1):
    d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)


def header(d, lt, num, eyebrow, title, sub=None):
    text_in(d, (120, 96), f"{num}  ·  {eyebrow.upper()}", font(24, True), GOLD, lt, 0.1)
    text_in(d, (120, 134), title, font(64, heavy=True), INK, lt, 0.25, dy=34)
    p = ease((lt - 0.5) / 0.7)
    tw = d.textlength(title, font=font(64, heavy=True))
    d.rounded_rectangle((120, 222, 120 + max(1, tw * p), 228), radius=3, fill=TEAL)
    if sub:
        text_in(d, (120, 248), sub, font(30), MUTED, lt, 0.55)


# ---------------------------------------------------------------- backdrop
class Backdrop:
    def __init__(self):
        g = np.linspace(0, 1, H)[:, None, None]
        x = np.linspace(0, 1, W)[None, :, None]
        arr = np.array(BG1) * (1 - 0.6 * g - 0.4 * x) + np.array(BG2) * (0.6 * g + 0.4 * x)
        self.base = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")
        d = ImageDraw.Draw(self.base)
        for yy in range(30, H, 48):  # subtle dot grid
            for xx in range(30, W, 48):
                d.ellipse((xx - 1, yy - 1, xx + 1, yy + 1), fill=(24, 84, 92))
        rnd = random.Random(11)
        self.glows = []
        for _ in range(4):
            r = rnd.randint(260, 420)
            b = r // 2
            spr = Image.new("L", (2 * r + 4 * b, 2 * r + 4 * b), 0)
            ImageDraw.Draw(spr).ellipse((2 * b, 2 * b, 2 * b + 2 * r, 2 * b + 2 * r), fill=rnd.randint(22, 38))
            spr = spr.filter(ImageFilter.GaussianBlur(b))
            col = rnd.choice([TEAL, GOLD, BLUE])
            self.glows.append((spr, Image.new("RGB", spr.size, col), rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(0, 6.3), rnd.uniform(0.05, 0.12)))

    def frame(self, t):
        img = self.base.copy()
        for spr, col, x, y, ph, sp in self.glows:
            cx = x + math.sin(t * sp + ph) * 220
            cy = y + math.cos(t * sp * 0.8 + ph) * 140
            img.paste(col, (int(cx - spr.width / 2), int(cy - spr.height / 2)), spr)
        return img


# ---------------------------------------------------------------- icons
def logo(d, cx, cy, s, p=1.0):
    rrect(d, (cx - s, cy - s, cx + s, cy + s), int(s * 0.55), fill=TEAL)
    pts = [(-0.55, 0.45), (-0.2, 0.45), (-0.2, 0.1), (0.15, 0.1), (0.15, -0.25), (0.5, -0.25)]
    pts = [(cx + x * s, cy + y * s) for x, y in pts]
    seg = (len(pts) - 1) * ease(p)
    for i in range(len(pts) - 1):
        if seg <= i:
            break
        q = min(1, seg - i)
        a, b = pts[i], pts[i + 1]
        d.line((a[0], a[1], a[0] + (b[0] - a[0]) * q, a[1] + (b[1] - a[1]) * q), fill=WHITE, width=max(3, int(s * 0.16)))
    if p > 0.85:
        r = s * 0.15
        d.ellipse((cx + 0.5 * s - r, cy - 0.62 * s - r, cx + 0.5 * s + r, cy - 0.62 * s + r), fill=GOLD)


def check(d, cx, cy, r, p, col=TEAL):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=col, width=3)
    if p <= 0:
        return
    a, b, c = (cx - r * 0.45, cy), (cx - r * 0.1, cy + r * 0.38), (cx + r * 0.5, cy - r * 0.35)
    q1 = min(1, p * 2)
    d.line((a[0], a[1], a[0] + (b[0] - a[0]) * q1, a[1] + (b[1] - a[1]) * q1), fill=col, width=5)
    if p > 0.5:
        q2 = (p - 0.5) * 2
        d.line((b[0], b[1], b[0] + (c[0] - b[0]) * q2, b[1] + (c[1] - b[1]) * q2), fill=col, width=5)


def cross(d, cx, cy, r, col=CORAL):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=col, width=3)
    k = r * 0.38
    d.line((cx - k, cy - k, cx + k, cy + k), fill=col, width=5)
    d.line((cx - k, cy + k, cx + k, cy - k), fill=col, width=5)


def connector(d, a, b, lt, delay, dur=0.7, col=TEAL, flow=True, label=None, speed=0.45):
    if lt < delay:
        return
    p = ease((lt - delay) / dur)
    x, y = a[0] + (b[0] - a[0]) * p, a[1] + (b[1] - a[1]) * p
    d.line((a[0], a[1], x, y), fill=lerp(BG1, col, 0.55), width=4)
    if flow and p >= 1:
        for k in range(3):
            q = (lt * speed + k / 3) % 1
            px, py = a[0] + (b[0] - a[0]) * q, a[1] + (b[1] - a[1]) * q
            d.ellipse((px - 6, py - 6, px + 6, py + 6), fill=col)
    if label and p > 0.9:
        f = font(20, True)
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        tw = d.textlength(label, font=f)
        rrect(d, (mx - tw / 2 - 10, my - 16, mx + tw / 2 + 10, my + 16), 14, fill=BG1, outline=lerp(BG1, col, 0.6))
        d.text((mx - tw / 2, my - 13), label, font=f, fill=col)


def node(d, cx, cy, w, h, title, sub, col, lt, delay, icon=None):
    if lt < delay:
        return
    p = back((lt - delay) / 0.55)
    ww, hh = w * p, h * p
    rrect(d, (cx - ww / 2, cy - hh / 2, cx + ww / 2, cy + hh / 2), 22, fill=CARD, outline=col, width=3)
    if p > 0.85:
        y = cy - h / 2 + 22
        if icon:
            ctext(d, cx, y - 4, icon, font(34), col)
            y += 44
        ctext(d, cx, y, title, font(28, True), INK)
        for i, ln in enumerate(sub.split("\n")):
            ctext(d, cx, y + 40 + i * 28, ln, font(21), MUTED)


# ---------------------------------------------------------------- scenes
def s_title(d, img, lt, dur):
    # rising steps
    for i, hgt in enumerate((0.22, 0.36, 0.5, 0.64)):
        p = ease((lt - 0.2 - i * 0.15) / 1.0)
        x0 = 1180 + i * 150
        top = H - (H * hgt) * p
        glow = 0.5 + 0.5 * math.sin(lt * 2 - i * 0.9)
        d.rectangle((x0, top, x0 + 146, H), fill=lerp(CARD, CARD2, glow * 0.6))
        d.rectangle((x0, top, x0 + 146, top + 4), fill=GOLD if i == 3 else lerp(LINE, TEAL, glow))
    logo(d, 200, 360, 70, (lt - 0.2) / 1.2)
    text_in(d, (120, 470), "Tamheed", font(140, heavy=True), INK, lt, 0.6, dy=40)
    text_in(d, (126, 650), "Behind the AI onboarding agent", font(46, True), TEAL, lt, 1.1)
    text_in(d, (126, 930), "RIMAL ENGINEERING & TECHNOLOGY", font(24, True), GOLD, lt, 2.0)


def s_problem(d, img, lt, dur):
    header(d, lt, "01", "Why", "From checklists to a personal agent")
    left = ["Same checklist for everyone", "PDFs and links nobody reads", "No idea if people are ready"]
    right = ["A plan built from each CV", "Personal video, tasks & courses", "Practice, feedback & adaptation"]
    rrect(d, (120, 340, 860, 900), 28, fill=CARD)
    rrect(d, (1060, 340, 1800, 900), 28, fill=CARD, outline=TEAL, width=3)
    text_in(d, (170, 380), "Onboarding today", font(36, True), MUTED, lt, 0.6, bg=CARD)
    text_in(d, (1110, 380), "With Tamheed", font(36, True), TEAL, lt, 0.9, bg=CARD)
    for i, s in enumerate(left):
        dl = 1.1 + i * 0.4
        text_in(d, (230, 500 + i * 120), s, font(32), lerp(MUTED, DIM, ease((lt - 4) / 1)), lt, dl, bg=CARD)
        if lt > dl:
            cross(d, 190, 522 + i * 120, 20, lerp(CARD, CORAL, ease((lt - dl) / 0.5)))
        if lt > 3.6 + i * 0.25:  # strike-through
            q = ease((lt - 3.6 - i * 0.25) / 0.5)
            tw = d.textlength(s, font=font(32))
            d.line((230, 524 + i * 120, 230 + tw * q, 524 + i * 120), fill=CORAL, width=3)
    for i, s in enumerate(right):
        dl = 4.4 + i * 0.45
        text_in(d, (1170, 500 + i * 120), s, font(32, True), INK, lt, dl, bg=CARD)
        if lt > dl:
            check(d, 1130, 522 + i * 120, 20, ease((lt - dl) / 0.6))
    if lt > 3.8:  # arrow
        p = ease((lt - 3.8) / 0.7)
        x1 = 900 + 120 * p
        d.line((890, 620, x1, 620), fill=GOLD, width=8)
        if p > 0.9:
            d.polygon([(x1 + 4, 620), (x1 - 22, 600), (x1 - 22, 640)], fill=GOLD)


def s_arch(d, img, lt, dur):
    header(d, lt, "01", "Architecture", "How it connects")
    web, api, db = (300, 600), (860, 600), (860, 900)
    worker, claude, studio, mail = (1380, 600), (1640, 380), (1700, 640), (1640, 880)
    connector(d, (web[0] + 150, web[1]), (api[0] - 150, api[1]), lt, 0.99, label="HTTPS · JSON")
    connector(d, (api[0], api[1] + 80), (db[0], db[1] - 70), lt, 1.49, col=GOLD, label="SQL")
    connector(d, (api[0] + 150, api[1]), (worker[0] - 130, worker[1]), lt, 1.98, label="jobs")
    connector(d, (worker[0] + 60, worker[1] - 70), (claude[0] - 120, claude[1] + 20), lt, 2.60, col=BLUE, label="tool calls")
    connector(d, (worker[0] + 130, worker[1]), (studio[0] - 140, studio[1]), lt, 3.10, col=CORAL, label="MP4")
    connector(d, (worker[0] + 60, worker[1] + 70), (mail[0] - 120, mail[1] - 20), lt, 3.60, col=GOLD, label="invite")
    connector(d, (worker[0] - 40, worker[1] + 80), (db[0] + 150, db[1] - 10), lt, 4.09, col=GOLD, flow=True)
    node(d, *web, 260, 130, "Website", "React", TEAL, lt, 0.50)
    node(d, *api, 280, 130, "Backend API", "FastAPI", TEAL, lt, 0.87)
    node(d, *db, 280, 130, "Database", "company data", GOLD, lt, 1.36)
    node(d, *worker, 240, 130, "Pipeline", "job queue", TEAL, lt, 1.86)
    node(d, *claude, 240, 150, "Claude agent", "Anthropic API", BLUE, lt, 2.48)
    node(d, *studio, 280, 150, "Video studio", "FFmpeg", CORAL, lt, 2.98)
    node(d, *mail, 240, 150, "Email", "Gmail SMTP", GOLD, lt, 3.47)
    # data chips stored in the DB
    chips = ["21 staff", "5 projects", "34 emails", "22 documents", "42 courses", "10 roles"]
    x = 520
    for i, c in enumerate(chips):
        dl = 4.8 + i * 0.18
        if lt < dl:
            continue
        p = back((lt - dl) / 0.4)
        f = font(22, True)
        tw = d.textlength(c, font=f)
        y = 1000
        rrect(d, (x, y - 18 * p, x + tw + 30, y + 18 * p), 18, fill=CARD2)
        if p > 0.8:
            d.text((x + 15, y - 14), c, font=f, fill=GOLD)
        x += tw + 44


def s_pipeline(d, img, lt, dur):
    header(d, lt, "03", "Automation", "From “Save” to a ready workspace", "Every step is a saved job: it survives restarts, retries on failure, never duplicates")
    steps = ["Record saved", "CV & team read", "Agent plans", "Tasks & equipment", "Mentoring", "Training",
             "Practical exercise", "Welcome video", "Workspace ready", "Invitation email"]
    cols, x0, y0, cw, ch = 5, 140, 380, 320, 210
    speed = (dur - 3.5) / len(steps)
    for i, s in enumerate(steps):
        r, c = divmod(i, cols)
        x, y = x0 + c * (cw + 30), y0 + r * (ch + 40)
        dl = 0.8 + i * 0.12
        if lt < dl:
            continue
        p = back((lt - dl) / 0.5)
        done_t = 1.8 + i * speed
        done = lt > done_t
        active = done_t - speed < lt <= done_t
        fill = CARD2 if active else CARD
        rrect(d, (x, y + (1 - p) * 30, x + cw, y + ch + (1 - p) * 30), 22, fill=fill, outline=TEAL if done else (GOLD if active else LINE), width=3)
        d.text((x + 26, y + 22), f"{i + 1:02d}", font=font(30, heavy=True), fill=GOLD if active else (TEAL if done else DIM))
        for j, ln in enumerate(wrap(d, s, font(30, True), cw - 50)):
            d.text((x + 26, y + 80 + j * 38), ln, font=font(30, True), fill=INK if (done or active) else MUTED)
        if done:
            check(d, x + cw - 46, y + 44, 22, ease((lt - done_t) / 0.4))
        elif active:
            a = lt * 6
            d.arc((x + cw - 68, y + 22, x + cw - 24, y + 66), a * 57 % 360, (a * 57 + 260) % 360, fill=GOLD, width=5)
        if i in (2, 6) and lt > dl:
            badge = "Claude" if True else ""
            f = font(18, True)
            rrect(d, (x + 26, y + ch - 46, x + 26 + d.textlength(badge, font=f) + 24, y + ch - 16), 14, fill=BLUE)
            d.text((x + 38, y + ch - 44), badge, font=f, fill=BG1)
    text_in(d, (140, 960), "≈ 1–2 minutes, fully automatic — HR watches it happen live", font(30, True), TEAL, lt, dur - 4)


FEED = [("tool", "Read profile and CV"), ("tool", "Loaded role requirements"), ("tool", "Looked up the team"),
        ("tool", "Searched the web for courses"), ("decision", "Mentor: Omar Haddad"), ("decision", "3 courses chosen")]


def s_agent(d, img, lt, dur):
    header(d, lt, "02", "The agent", "One Claude agent, many tools")
    cx, cy, R = 560, 640, 270
    tools = [("Profile & CV", TEAL), ("Role requirements", TEAL), ("Team & mentors", GOLD),
             ("Course catalog", GOLD), ("Company records", CORAL), ("Web search", BLUE)]
    active = int((lt - 1.4) / 0.9) % len(tools) if lt > 1.4 and lt < dur - 2.5 else -1
    for i, (name, col) in enumerate(tools):
        a = -math.pi / 2 + i * 2 * math.pi / len(tools) + lt * 0.05
        tx, ty = cx + math.cos(a) * R, cy + math.sin(a) * R * 0.8
        on = i == active
        connector(d, (cx, cy), (tx, ty), lt, 0.9 + i * 0.12, col=col if on else LINE, flow=on, speed=1.2)
        dl = 0.9 + i * 0.12
        if lt > dl:
            p = back((lt - dl) / 0.5)
            f = font(24, True)
            tw = d.textlength(name, font=f)
            w2 = (tw / 2 + 24) * p
            rrect(d, (tx - w2, ty - 30 * p, tx + w2, ty + 30 * p), 30, fill=col if on else CARD, outline=col, width=3)
            if p > 0.8:
                d.text((tx - tw / 2, ty - 16), name, font=f, fill=BG1 if on else INK)
    pulse = 1 + 0.05 * math.sin(lt * 4)
    rr = 110 * back((lt - 0.5) / 0.6) * pulse
    if lt > 0.5:
        d.ellipse((cx - rr - 16, cy - rr - 16, cx + rr + 16, cy + rr + 16), outline=lerp(BG1, BLUE, 0.6), width=3)
        d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), fill=BLUE)
        ctext(d, cx, cy - 40, "Claude", font(40, heavy=True), BG1)
        ctext(d, cx, cy + 10, "reasons & plans", font(24, True), BG1)
    # live feed panel
    px0, py0 = 1080, 330
    rrect(d, (px0, py0, 1800, 1000), 26, fill=CARD)
    d.ellipse((px0 + 30, py0 + 34, px0 + 44, py0 + 48), fill=TEAL if int(lt * 2) % 2 else lerp(CARD, TEAL, 0.4))
    d.text((px0 + 58, py0 + 24), "Live activity", font=font(26, True), fill=INK)
    shown = min(len(FEED), max(0, int((lt - 1.4) / 1.15)))
    icons = {"tool": ("🔧", TEAL), "thinking": ("💭", MUTED), "decision": ("✅", INK), "warning": ("🚩", GOLD)}
    y = py0 + 90
    for k, (kind, txt) in enumerate(FEED[:shown]):
        age = lt - 1.4 - k * 1.15
        p = ease(age / 0.4)
        ic, col = icons[kind]
        f = mono(24) if kind == "tool" else font(28, True)
        lines = wrap(d, txt, f, 600)
        d.text((px0 + 30, y + (1 - p) * 10), "›", font=font(26, True), fill=lerp(CARD, col, p))
        for j, ln in enumerate(lines[:2]):
            d.text((px0 + 60, y + j * 28 + (1 - p) * 10), ln, font=f, fill=lerp(CARD, col, p))
        y += 36 * min(2, len(lines)) + 40
    if lt > dur - 2.4:
        p = back((lt - dur + 2.4) / 0.6)
        rrect(d, (240, 960 - 40 * p, 880, 960 + 40 * p), 40, fill=TEAL)
        if p > 0.8:
            ctext(d, 560, 940, "plan  →  checked  →  saved", mono(26, True), BG1)


CODE = '''TOOLS = [get_new_hire_profile, get_role_requirements, get_team,
         search_course_catalog, search_company_records, web_search]

for turn in range(MAX_TURNS):
    resp = client.messages.create(model=MODEL, system=SYSTEM,
                                  tools=TOOLS + [SUBMIT_PLAN], messages=msgs)
    for call in tool_calls(resp):
        if call.name == "submit_onboarding_plan":
            plan, issues = validate(ctx, call.input)   # guardrails
            if issues and first_try:
                send_back(issues)                      # agent fixes once
            else:
                return plan                            # saved to database
        result = run_tool(ctx, call.name, call.input)  # scoped to this hire
        log(case, "tool", summary(result))             # live feed for HR'''

NOTES = [(0, "Tools", TEAL), (5, "Claude decides", BLUE), (8, "Checked first", GOLD), (14, "Shown live", CORAL)]


def s_code(d, img, lt, dur):
    header(d, lt, "03", "Code", "The agent loop")
    x0, y0, x1, y1 = 120, 320, 1340, 1010
    rrect(d, (x0, y0, x1, y1), 24, fill=(10, 34, 40), outline=LINE, width=2)
    for i, c in enumerate((CORAL, GOLD, TEAL)):
        d.ellipse((x0 + 26 + i * 30, y0 + 22, x0 + 44 + i * 30, y0 + 40), fill=c)
    d.text((x0 + 130, y0 + 16), "app/agent.py", font=mono(20), fill=MUTED)
    lines = CODE.split("\n")
    shown_chars = int(max(0, lt - 0.8) * 230)
    colors = {Keyword: BLUE, Name.Function: TEAL, Name.Builtin: TEAL, String: GOLD, Comment: (110, 150, 150), Number: CORAL, Operator: MUTED}
    f = mono(24)
    y, used = y0 + 74, 0
    hl = int((lt - 5.2) / 1.2) % 4 if lt > 5.2 else -1
    if hl >= 0:
        ln_i = NOTES[hl][0]
        span = 2 if ln_i in (0, 5) else 1
        d.rectangle((x0 + 4, y0 + 70 + ln_i * 38, x1 - 4, y0 + 70 + (ln_i + span) * 38), fill=(20, 60, 68))
    for li, line in enumerate(lines):
        x = x0 + 40
        d.text((x0 + 12, y), f"{li + 1:>2}", font=mono(18), fill=DIM)
        for tok, val in lex(line, PythonLexer()):
            val = val.rstrip("\n")
            if not val:
                continue
            take = max(0, min(len(val), shown_chars - used))
            used += len(val)
            col = next((c for k, c in colors.items() if tok in k), INK)
            if take:
                d.text((x, y), val[:take], font=f, fill=col)
            x += d.textlength(val, font=f)
        used += 1
        y += 38
    if shown_chars < len(CODE) and int(lt * 3) % 2:  # cursor
        d.rectangle((x0 + 40, y0 + 74, x0 + 52, y0 + 100), fill=TEAL)
    for i, (ln, txt, col) in enumerate(NOTES):
        dl = 2.0 + i * 0.6
        if lt < dl:
            continue
        p = ease((lt - dl) / 0.5)
        yy = y0 + 70 + ln * 38
        on = hl == i
        rrect(d, (1390 + (1 - p) * 40, yy - 6, 1800, yy + 56), 18, fill=col if on else CARD, outline=col, width=2)
        d.text((1414 + (1 - p) * 40, yy + 8), txt, font=font(24, True), fill=BG1 if on else INK)
        d.line((x1, yy + 25, 1390, yy + 25), fill=lerp(BG1, col, p * 0.7), width=2)


RULES = [("Evidence must be quoted from the CV", ""), ("Courses & links must be real", ""),
         ("Mentors must be real colleagues", ""), ("No Claude? Simple rules take over", "")]


def s_rules(d, img, lt, dur):
    header(d, lt, "04", "Rules", "Claude proposes, rules decide")
    # shield
    cx, cy = 360, 650
    p = back((lt - 0.6) / 0.7)
    if lt > 0.6:
        s = 170 * p
        pts = [(cx, cy - s), (cx + s * 0.85, cy - s * 0.6), (cx + s * 0.75, cy + s * 0.35), (cx, cy + s), (cx - s * 0.75, cy + s * 0.35), (cx - s * 0.85, cy - s * 0.6)]
        d.polygon(pts, fill=CARD2, outline=TEAL)
        d.line(pts + [pts[0]], fill=TEAL, width=5)
        if p > 0.8:
            check(d, cx, cy - 10, 70, ease((lt - 1.2) / 0.8), GOLD)
    for i, (a, b) in enumerate(RULES):
        dl = 1.0 + i * 1.1
        y = 360 + i * 150
        if lt < dl:
            continue
        q = ease((lt - dl) / 0.5)
        rrect(d, (720 + (1 - q) * 50, y, 1800, y + 112), 24, fill=CARD)
        check(d, 780 + (1 - q) * 50, y + 56, 26, ease((lt - dl - 0.2) / 0.5))
        d.text((840 + (1 - q) * 50, y + 34), a, font=font(38, True), fill=lerp(CARD, INK, q))
    if False:  # (rejection example removed for a simpler video)
        q = back((lt - dur + 4.2) / 0.6)
        rrect(d, (130, 870 - 60 * (1 - q), 600, 1010), 20, fill=PINK)
        if q > 0.8:
            d.text((160, 892), "Rejected by the validator", font=font(22, True), fill=CORAL)
            d.text((160, 928), "“Led a 400 kV grid design”", font=font(22), fill=(90, 40, 34))
            d.text((160, 960), "not in the CV  ›  not shown yet", font=font(22, True), fill=(90, 40, 34))


def browser(d, x0, y0, x1, y1, url):
    rrect(d, (x0, y0, x1, y1), 22, fill=PAPER)
    rrect(d, (x0, y0, x1, y0 + 56), 22, fill=(226, 234, 234))
    d.rectangle((x0, y0 + 34, x1, y0 + 56), fill=(226, 234, 234))
    for i, c in enumerate((CORAL, GOLD, TEAL)):
        d.ellipse((x0 + 22 + i * 26, y0 + 20, x0 + 38 + i * 26, y0 + 36), fill=c)
    rrect(d, (x0 + 120, y0 + 14, x1 - 40, y0 + 42), 14, fill=WHITE)
    d.text((x0 + 140, y0 + 16), url, font=font(18), fill=(90, 110, 112))


def view_prep(d, x0, y0, w, h, lt):
    d.text((x0 + 40, y0 + 90), "Preparing Layan's onboarding…", font=font(34, True), fill=(15, 42, 46))
    steps = ["CV & team read", "Agent plans", "Mentoring", "Training", "Practical exercise", "Welcome video"]
    for i, s in enumerate(steps):
        y = y0 + 160 + i * 64
        done = lt > 0.6 + i * 0.6
        d.ellipse((x0 + 40, y, x0 + 72, y + 32), fill=(31, 138, 91) if done else WHITE, outline=(200, 214, 214), width=2)
        d.text((x0 + 90, y), s, font=font(24, done), fill=(15, 42, 46) if done else (120, 140, 140))
    rrect(d, (x0 + w * 0.5, y0 + 150, x0 + w - 40, y0 + h - 40), 18, fill=WHITE, outline=(222, 232, 232))
    d.ellipse((x0 + w * 0.5 + 24, y0 + 176, x0 + w * 0.5 + 38, y0 + 190), fill=(31, 138, 91))
    d.text((x0 + w * 0.5 + 48, y0 + 168), "Onboarding agent — live", font=font(22, True), fill=(31, 138, 91))
    for k, (kind, txt) in enumerate(FEED[: min(len(FEED), int(lt / 0.5))][-7:]):
        d.text((x0 + w * 0.5 + 24, y0 + 214 + k * 46), ("› " if kind == "tool" else "• ") + txt[:44], font=font(19), fill=(13, 92, 99) if kind == "tool" else (40, 60, 64))


def view_dash(d, img, x0, y0, w, h, lt, frames):
    rrect(d, (x0 + 30, y0 + 80, x0 + w - 30, y0 + 200), 22, fill=(13, 92, 99))
    d.text((x0 + 60, y0 + 100), "WELCOME TO RIMAL", font=font(18, True), fill=GOLD)
    d.text((x0 + 60, y0 + 126), "Welcome, Layan!", font=font(44, heavy=True), fill=WHITE)
    vw = w - 60
    vh = int(vw * 9 / 16)
    vh = min(vh, h - 240)
    vw = int(vh * 16 / 9)
    if frames:
        fr = frames[int(lt * 15) % len(frames)].resize((vw, vh))
        img.paste(fr, (int(x0 + (w - vw) / 2), int(y0 + 220)))


def view_exercise(d, x0, y0, w, h, lt):
    d.text((x0 + 40, y0 + 90), "Practical exercise", font=font(34, True), fill=(15, 42, 46))
    rrect(d, (x0 + 40, y0 + 150, x0 + w - 40, y0 + 330), 16, fill=WHITE, outline=(222, 232, 232))
    d.text((x0 + 64, y0 + 168), "Check a Draft Bay 3 Relay Test Plan", font=font(26, True), fill=(15, 42, 46))
    for i, row in enumerate(["Register check 24 h before inspection", "Settings follow PP-04", "Export by 15 October"]):
        d.text((x0 + 64, y0 + 212 + i * 36), f"{i + 1}  {row}", font=font(20), fill=(60, 80, 84))
    p = ease((lt - 1.2) / 1.6)
    cx, cy, r = x0 + 150, y0 + 450, 90
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(222, 232, 232), width=14)
    d.arc((cx - r, cy - r, cx + r, cy + r), -90, -90 + 360 * 0.96 * p, fill=(13, 92, 99), width=14)
    ctext(d, cx, cy - 26, f"{int(96 * p)}%", font(40, heavy=True), (15, 42, 46))
    d.text((x0 + 280, y0 + 400), "AI-assessed", font=font(20, True), fill=(13, 92, 99))
    for j, ln in enumerate(wrap(d, "Great work — you found both mistakes and cited E4 and E5. More independence on ITPs unlocked.", font(22), w - 340)):
        d.text((x0 + 280, y0 + 434 + j * 32), ln, font=font(22), fill=(40, 60, 64))


def s_website(d, img, lt, dur, frames=None):
    header(d, lt, "05", "Website", "Where it shows up")
    views = [("HR · live preparation", "", "localhost/#/hr/prep"),
             ("Employee · welcome video", "", "localhost/#/me"),
             ("Employee · practical exercise", "", "localhost/#/me/exercise")]
    seg = (dur - 1.2) / len(views)
    k = min(len(views) - 1, int(max(0, lt - 1.0) / seg))
    vlt = lt - 1.0 - k * seg
    # left labels
    for i, (title, sub, _) in enumerate(views):
        y = 380 + i * 170
        on = i == k
        rrect(d, (120, y + 20, 640, y + 110), 22, fill=CARD2 if on else CARD, outline=TEAL if on else LINE, width=3)
        d.text((150, y + 44), title, font=font(30, True), fill=INK if on else MUTED)
        for j, ln in enumerate(wrap(d, sub, font(22), 460)):
            d.text((150, y + 70 + j * 30), ln, font=font(22), fill=TEAL if on else DIM)
        if on:
            d.line((640, y + 70, 700, y + 70), fill=TEAL, width=4)
    x0, y0, x1, y1 = 700, 330, 1800, 1010
    p = ease((lt - 0.8) / 0.6)
    if p <= 0:
        return
    browser(d, x0, y0 + (1 - p) * 40, x1, y1, views[k][2])
    fade = ease(vlt / 0.35)
    if fade > 0.05:
        if k == 0:
            view_prep(d, x0, y0, x1 - x0, y1 - y0, vlt)
        elif k == 1:
            view_dash(d, img, x0, y0, x1 - x0, y1 - y0, vlt, frames)
        else:
            view_exercise(d, x0, y0, x1 - x0, y1 - y0, vlt)


def s_loop(d, img, lt, dur):
    header(d, lt, "08", "Adaptation", "It keeps learning about each person")
    steps = [("Plan", TEAL), ("Learn", TEAL), ("Practise", GOLD), ("Assess", GOLD), ("Adapt", BLUE), ("Complete", TEAL), ("Existing employee", GOLD)]
    cx, cy, R = 600, 650, 330
    n = len(steps)
    for i in range(n):
        a1 = -math.pi / 2 + i * 2 * math.pi / n
        a2 = -math.pi / 2 + (i + 1) * 2 * math.pi / n
        if lt > 0.6 + i * 0.25:
            d.arc((cx - R, cy - R * 0.85, cx + R, cy + R * 0.85), math.degrees(a1) + 8, math.degrees(a2) - 8, fill=LINE, width=4)
    dot = (lt * 0.18) % 1
    ad = -math.pi / 2 + dot * 2 * math.pi
    for i, (name, col) in enumerate(steps):
        a = -math.pi / 2 + i * 2 * math.pi / n
        x, y = cx + math.cos(a) * R, cy + math.sin(a) * R * 0.85
        dl = 0.6 + i * 0.25
        if lt < dl:
            continue
        p = back((lt - dl) / 0.5)
        near = abs(((ad - a + math.pi) % (2 * math.pi)) - math.pi) < 0.45
        f = font(28, True)
        tw = d.textlength(name, font=f)
        rrect(d, (x - (tw / 2 + 28) * p, y - 36 * p, x + (tw / 2 + 28) * p, y + 36 * p), 36, fill=col if near else CARD, outline=col, width=3)
        if p > 0.8:
            d.text((x - tw / 2, y - 18), name, font=f, fill=BG1 if near else INK)
    x, y = cx + math.cos(ad) * R, cy + math.sin(ad) * R * 0.85
    d.ellipse((x - 12, y - 12, x + 12, y + 12), fill=WHITE)
    ctext(d, cx, cy - 34, "Plan  ›  Practise", font(30, True), lerp(BG1, MUTED, ease((lt - 1) / 1)))
    ctext(d, cx, cy + 8, "› Adapt", font(30, True), lerp(BG1, MUTED, ease((lt - 1.3) / 1)))
    examples = [("HR changes the project", "agent re-plans mentors, tasks & video", TEAL),
                ("Employee finishes a course", "agent reviews progress & suggests the next step", BLUE),
                ("Exercise scored 96%", "more independence on that responsibility", GOLD),
                ("Everything required is done", "HR is notified · moves to existing after 3 weeks", CORAL)]
    for i, (a, b, col) in enumerate(examples):
        dl = 2.0 + i * 0.8
        if lt < dl:
            continue
        q = ease((lt - dl) / 0.5)
        y0 = 340 + i * 160
        rrect(d, (1080 + (1 - q) * 60, y0, 1800, y0 + 136), 22, fill=CARD, outline=col, width=3)
        d.text((1112 + (1 - q) * 60, y0 + 24), a, font=font(30, True), fill=lerp(CARD, INK, q))
        d.text((1112 + (1 - q) * 60, y0 + 74), b, font=font(24), fill=lerp(CARD, col, q))


def s_close(d, img, lt, dur):
    stats = []
    _unused = [("10", "job roles"), ("42", "courses + web search"), ("14", "automated tests"), ("0", "invented links accepted")]
    for i, (n, l) in enumerate(stats):
        dl = 0.4 + i * 0.3
        if lt < dl:
            continue
        p = back((lt - dl) / 0.6)
        x = 150 + i * 420
        rrect(d, (x, 320 + (1 - p) * 40, x + 380, 540 + (1 - p) * 40), 26, fill=CARD)
        cnt = int(int(n) * ease((lt - dl) / 1.2)) if n.isdigit() else n
        d.text((x + 34, 340 + (1 - p) * 40), str(cnt), font=font(96, heavy=True), fill=[TEAL, GOLD, BLUE, CORAL][i])
        d.text((x + 38, 476 + (1 - p) * 40), l, font=font(26, True), fill=MUTED)
    logo(d, 960, 380, 80, (lt - 0.3) / 1.0)
    if lt > 0.8:
        p = ease((lt - 0.8) / 0.8)
        ctext(d, 960, 500 + (1 - p) * 20, "Tamheed", font(110, heavy=True), lerp(BG1, INK, p))
    if lt > 1.5:
        p = ease((lt - 1.5) / 0.8)
        ctext(d, 960, 670, "A confident start. A future of possibilities.", font(40, True), lerp(BG1, TEAL, p))
    if lt > 2.2:
        ctext(d, 960, 750, "RIMAL ENGINEERING & TECHNOLOGY", font(24, True), lerp(BG1, GOLD, ease((lt - 2.2) / 0.8)))


SCENES = [(5.0, s_title), (10.0, s_arch), (11.0, s_agent), (10.0, s_code), (8.0, s_rules), (11.5, s_website), (5.0, s_close)]


def load_frames():
    vids = sorted((ROOT / "data" / "storage" / "employees").glob("*/video_v*.mp4"))
    if not vids:
        return []
    tmp = OUT_DIR / "clip"
    tmp.mkdir(parents=True, exist_ok=True)
    for f in tmp.glob("*.png"):
        f.unlink()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "4", "-t", "6", "-i", str(vids[-1]), "-vf", "fps=15,scale=960:-1", str(tmp / "f%03d.png")], check=True)
    return [Image.open(p).convert("RGB") for p in sorted(tmp.glob("*.png"))]


def render_frame(bd, t, frames):
    acc = 0.0
    for dur, fn in SCENES:
        if t < acc + dur:
            lt = t - acc
            img = bd.frame(t)
            d = ImageDraw.Draw(img)
            if fn is s_website:
                fn(d, img, lt, dur, frames)
            else:
                fn(d, img, lt, dur)
            fade = min(1, lt / 0.45, (dur - lt) / 0.45)
            if fade < 1:
                img = Image.blend(Image.new("RGB", (W, H), BG1), img, max(0, fade))
            # progress line
            ImageDraw.Draw(img).rectangle((0, H - 6, W * t / total(), H), fill=TEAL)
            return img
        acc += dur
    return bd.frame(t)


def total():
    return sum(d for d, _ in SCENES)


def main():
    out = Path(sys.argv[1])
    frames = load_frames()
    bd = Backdrop()
    if "--frames" in sys.argv:
        ts = [float(x) for x in sys.argv[sys.argv.index("--frames") + 1].split(",")]
        for t in ts:
            render_frame(bd, t, frames).resize((960, 540)).save(out.parent / f"still_{t:05.1f}.png")
        return
    music = OUT_DIR / "music.wav"
    T = total()
    subprocess.run([sys.executable, str(Path(__file__).with_name("music.py")), str(music), str(T)], check=True)
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", str(music), "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = int(T * FPS)
    for i in range(n):
        p.stdin.write(render_frame(bd, i / FPS, frames).tobytes())
        if i % (FPS * 10) == 0:
            print(f"{i / FPS:5.0f}s / {T:.0f}s", flush=True)
    p.stdin.close()
    p.wait()
    print("done", out)


if __name__ == "__main__":
    main()
