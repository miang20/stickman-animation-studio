#!/usr/bin/env python3
"""Free, deterministic 2D stickman cartoon renderer (no API keys or external assets)."""
from __future__ import annotations

import json
import math
import os
import random
import shutil
import subprocess
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
TMP = ROOT / ".render_tmp"
SCRIPT = ROOT / "scripts" / "episode.json"
FPS = 24
W, H = (1920, 1080) if os.getenv("RESOLUTION", "720p") == "1080p" else (1280, 720)
DURATION_MINUTES = max(1, min(8, int(os.getenv("DURATION_MINUTES", "5"))))
VOICE_ON = os.getenv("VOICE", "on").lower() == "on"
COLOR_THEME = os.getenv("CHARACTER_COLOR", "blue").lower()
CHARACTER_COLORS = {
    "blue": "#2588e8", "cyan": "#20c7d9", "red": "#e44747",
    "green": "#2da66f", "purple": "#8855d9", "orange": "#f08a32",
    "yellow": "#e8c33b", "pink": "#e65caa", "white": "#e8edf4",
    "black": "#343943",
}
SR = 22050
random.seed(2026)

PALETTES = {
    "safehouse": ("#172337", "#34475d", "#f6c85f"),
    "bank": ("#b9d8e8", "#e9eef0", "#e0ad50"),
    "street": ("#14243b", "#405b76", "#f2c14e"),
    "police": ("#17263b", "#40556c", "#6dc5ff"),
    "warehouse": ("#302b38", "#5d5661", "#e0a458"),
    "roof": ("#26384b", "#7895a8", "#f4c95d"),
    "vault": ("#172b34", "#425c60", "#8ee3d0"),
    "control_room": ("#151e31", "#303c56", "#65d6ff"),
    "van": ("#243142", "#59616c", "#f4c95d"),
    "hall": ("#293444", "#536174", "#f4c95d"),
}


def font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, max(10, size))
    return ImageFont.load_default()


def rgb(value: str):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def clamp(value, low, high):
    return max(low, min(high, value))


def centered(draw, xy, text, fnt, fill, stroke_width=0, stroke_fill="#000000"):
    draw.text(xy, str(text), font=fnt, fill=fill, anchor="mm",
              stroke_width=stroke_width, stroke_fill=stroke_fill)


def wrap_words(text, max_chars=34):
    lines, line = [], ""
    for word in str(text).split():
        if len(line) + len(word) + bool(line) > max_chars:
            if line:
                lines.append(line)
            line = word
        else:
            line = (line + " " + word).strip()
    if line:
        lines.append(line)
    return lines or [""]


def make_background(setting):
    """Build each location once; reusing it avoids an expensive per-frame gradient."""
    sky, floor, accent = PALETTES.get(setting, PALETTES["safehouse"])
    top, bottom = rgb(sky), rgb(floor)
    gradient = np.empty((H, W, 3), dtype=np.uint8)
    for y in range(H):
        f = y / max(1, H - 1)
        gradient[y, :, :] = [int(top[k] * (1 - f) + bottom[k] * f) for k in range(3)]
    im = Image.fromarray(gradient, "RGB")
    d = ImageDraw.Draw(im)
    horizon = int(H * .70)

    if setting in ("street", "roof", "police"):
        bw = W // 9
        for i in range(-1, 11):
            x = i * bw
            bh = int(H * (.18 + ((i * 37) % 7) / 35))
            d.rectangle((x, horizon - bh, x + bw - 8, horizon), fill="#253348", outline="#172333", width=max(2, W // 500))
            for wy in range(horizon - bh + 24, horizon - 16, max(22, H // 22)):
                for wx in range(x + 15, x + bw - 15, max(22, W // 42)):
                    d.rectangle((wx, wy, wx + 9, wy + 13), fill=accent)
    elif setting == "bank":
        d.rectangle((W * .12, H * .22, W * .88, horizon), fill="#e5e1d8", outline="#596575", width=5)
        for x in np.linspace(W * .18, W * .82, 7):
            d.polygon([(x - 18, H * .30), (x + 18, H * .30), (x + 24, horizon), (x - 24, horizon)], fill="#f7f3e9", outline="#66717d")
        d.polygon([(W * .10, H * .23), (W * .5, H * .10), (W * .90, H * .23)], fill="#c9d0d7", outline="#66717d")
        centered(d, (W * .5, H * .18), "CENTRAL RESERVE", font(int(H * .032), True), "#28364a")
    elif setting in ("vault", "control_room"):
        d.rectangle((W * .08, H * .16, W * .92, horizon), fill="#253b46", outline="#101923", width=5)
        if setting == "vault":
            d.ellipse((W * .35, H * .23, W * .65, H * .61), fill="#82949a", outline="#d4e0df", width=max(8, W // 100))
            d.ellipse((W * .41, H * .29, W * .59, H * .55), fill="#354953", outline="#101923", width=5)
            d.ellipse((W * .47, H * .35, W * .53, H * .49), fill="#9bb4b8", outline="#17232a", width=4)
        else:
            for i in range(6):
                x = int(W * (.16 + i * .135))
                d.rounded_rectangle((x, H * .24, x + W * .09, H * .47), radius=8, fill="#172337", outline=accent, width=3)
                for j in range(3):
                    d.line((x + 12, H * (.29 + j * .05), x + W * .075, H * (.29 + j * .05)), fill="#47768a", width=3)
    else:
        d.rectangle((W * .05, H * .12, W * .95, horizon), fill="#354252", outline="#111a27", width=4)
        d.line((W * .05, H * .28, W * .95, H * .28), fill="#566477", width=3)
        for x in (W * .22, W * .5, W * .78):
            d.ellipse((x - 30, H * .14, x + 30, H * .17), fill="#ffe7a6")
            d.line((x, H * .17, x, H * .27), fill="#8d9aa8", width=3)
        if setting == "safehouse":
            bx, by, bw, bh = int(W * .58), int(H * .20), int(W * .32), int(H * .34)
            d.rounded_rectangle((bx, by, bx + bw, by + bh), radius=12, fill="#e4ddc9", outline="#151c26", width=5)
            for j in range(5):
                x1 = bx + 25 + j * bw // 5
                d.line((x1, by + 25, x1 + bw // 6, by + bh - 25), fill="#a5a18f", width=3)
            for j in range(4):
                y = by + 35 + j * bh // 4
                d.line((bx + 20, y, bx + bw - 20, y + 15), fill="#b0a894", width=3)
            for px, py in ((.66, .30), (.78, .39), (.84, .28), (.72, .47)):
                x, y = int(W * px), int(H * py)
                d.ellipse((x - 9, y - 9, x + 9, y + 9), fill="#cf4545", outline="#632b2b", width=2)
        elif setting == "warehouse":
            for x in range(int(W * .12), int(W * .9), int(W * .2)):
                d.rectangle((x, H * .39, x + W * .12, horizon), fill="#7d6852", outline="#332d2c", width=4)
                d.line((x, H * .45, x + W * .12, H * .45), fill="#b49a72", width=3)
    # perspective floor
    d.polygon([(0, horizon), (W, horizon), (W, H), (0, H)], fill="#303744")
    for x in range(0, W + 1, max(80, W // 10)):
        d.line((W * .5, horizon, x, H), fill="#3b4552", width=2)
    d.line((0, horizon, W, horizon), fill="#111923", width=5)
    # Foreground props create more visual variety across scene types.
    if setting in ("safehouse", "warehouse", "van"):
        for x in (W * .12, W * .84):
            d.rectangle((x, H * .57, x + W * .08, H * .70), fill="#6b5848", outline="#211f25", width=4)
            d.line((x, H * .62, x + W * .08, H * .62), fill="#9a8061", width=3)
    return im, accent


def draw_character(draw, c, x, ground, t, scale=1.0, action="idle", facing=1, accent="#f2c14e", name_tag=True):
    head = int(H * .060 * scale)
    torso = int(H * .155 * scale)
    limb = int(H * .12 * scale)
    line = max(4, int(H * .007 * scale))
    skin = c.get("accent", "#f0c6a2")
    # One workflow colour selector recolours every recurring character while preserving identity.
    outfit = CHARACTER_COLORS.get(COLOR_THEME, CHARACTER_COLORS["blue"])
    dark = "#141923"
    movement = {"walk": 1.0, "sneak": .6, "run": 1.7, "dash": 2.0}.get(action, 0.0)
    bob = int(math.sin(t * (9 if movement else 2.5)) * H * (.010 if movement else .003))
    y = int(ground + bob)
    shoulder_y, hip_y = y - torso, y - int(torso * .28)
    phase = math.sin(t * (9 if action in ("run", "dash") else 6)) * limb * .43 if movement else 0
    if action == "sneak":
        shoulder_y += int(H * .025)
        hip_y += int(H * .02)
    if action in ("fall", "trip"):
        shoulder_y += int(H * .09)
    # legs, with visible alternating steps
    leg1 = phase
    leg2 = -phase
    if action in ("fall", "trip"):
        leg1, leg2 = -limb * .35, limb * .35
    draw.line((x, hip_y, x - facing * limb * .34 + leg1, y + limb * .72), fill=outfit, width=line, joint="curve")
    draw.line((x, hip_y, x + facing * limb * .34 + leg2, y + limb * .72), fill=outfit, width=line, joint="curve")
    draw.line((x - facing * limb * .34 + leg1, y + limb * .72, x - facing * limb * .34 + leg1 + facing * line * 2, y + limb * .72), fill="#0d1118", width=line)
    draw.line((x + facing * limb * .34 + leg2, y + limb * .72, x + facing * limb * .34 + leg2 + facing * line * 2, y + limb * .72), fill="#0d1118", width=line)
    # torso and costume details
    draw.line((x, shoulder_y, x, hip_y), fill=outfit, width=max(line * 4, 14))
    draw.line((x - line, shoulder_y + 8, x - line, hip_y), fill="#f7e5d7", width=max(2, line // 2))
    draw.line((x - line * 2, shoulder_y + int(torso * .3), x + line * 2, shoulder_y + int(torso * .3)), fill="#f7e5d7", width=max(2, line // 2))
    arm_len = int(H * .105 * scale)
    if action in ("panic", "react", "surrender"):
        left = (x - arm_len * .75, shoulder_y - arm_len * .6)
        right = (x + arm_len * .75, shoulder_y - arm_len * .6)
    elif action in ("point", "aim"):
        left = (x - facing * arm_len * .7, shoulder_y + arm_len * .7)
        right = (x + facing * arm_len, shoulder_y - arm_len * .25)
    elif action in ("wave", "celebrate"):
        left = (x - arm_len * .65, shoulder_y - arm_len * .65)
        right = (x + arm_len * .65, shoulder_y - arm_len * .8 + math.sin(t * 10) * 12)
    elif action == "sneak":
        left, right = (x - arm_len * .6, shoulder_y + arm_len * .15), (x + arm_len * .6, shoulder_y + arm_len * .15)
    elif action in ("fall", "trip"):
        left, right = (x - arm_len, shoulder_y - arm_len * .15), (x + arm_len, shoulder_y + arm_len * .15)
    else:
        swing = math.sin(t * 7) * arm_len * .35 if movement else math.sin(t * 2) * arm_len * .05
        left, right = (x - arm_len * .6 + swing, shoulder_y + arm_len * .7), (x + arm_len * .6 - swing, shoulder_y + arm_len * .7)
    draw.line((x, shoulder_y + 8, *left), fill=outfit, width=line, joint="curve")
    draw.line((x, shoulder_y + 8, *right), fill=outfit, width=line, joint="curve")
    # hands
    for hx, hy in (left, right):
        rr = max(4, line // 2)
        draw.ellipse((hx - rr, hy - rr, hx + rr, hy + rr), fill=outfit, outline=dark, width=1)
    # head, hair and facial expression
    hy = shoulder_y - head - int(H * .014)
    # Signature reference look: oversized dark round head, bright expressive eyes,
    # bold coloured body and clean high-contrast outlines.
    draw.ellipse((x - head, hy - head, x + head, hy + head), fill="#11151d", outline="#05070a", width=max(line, 3))
    draw.arc((x - head * .72, hy - head * .72, x + head * .72, hy + head * .72), 205, 315, fill="#353c48", width=max(2, line // 3))
    # Clean silhouette: no spiky symbols; hair is a restrained curved shape that
    # follows the round head, so every character reads as an intentional cartoon.
    hair = c.get("hair", "short")
    if hair == "neat":
        draw.pieslice((x - head * .94, hy - head * .96, x + head * .94, hy + head * .38),
                      180, 355, fill="#1c2026")
    elif hair == "messy":
        draw.arc((x - head * .91, hy - head * .96, x + head * .91, hy + head * .50),
                 185, 350, fill="#292d35", width=max(3, line // 2))
    else:
        draw.arc((x - head * .92, hy - head * .94, x + head * .92, hy + head * .40),
                 185, 350, fill="#292d35", width=max(3, line // 2))
    eye_y, eye_dx = hy - int(head * .02), int(head * .34)
    eye_r = max(3, int(head * .095))
    for ex in (x - eye_dx, x + eye_dx):
        draw.ellipse((ex - eye_r, eye_y - eye_r, ex + eye_r, eye_y + eye_r), fill="#ffffff")
        draw.ellipse((ex - 2, eye_y - 2, ex + 3, eye_y + 3), fill=dark)
    if action in ("panic", "react", "surrender"):
        draw.ellipse((x - head * .19, hy + head * .23, x + head * .19, hy + head * .58), fill="#5b2525")
    elif action in ("celebrate", "wave"):
        draw.arc((x - head * .32, hy + head * .15, x + head * .32, hy + head * .62), 5, 175, fill=dark, width=max(2, line // 2))
    else:
        draw.arc((x - head * .32, hy + head * .17, x + head * .32, hy + head * .58), 5, 175, fill=dark, width=max(2, line // 2))
    # Restrained costume seam; no floating labels or badge-like symbols.
    draw.line((x - line * 1.2, shoulder_y + int(torso * .36),
               x + line * 1.2, shoulder_y + int(torso * .36)),
              fill="#f2d9a0", width=max(2, line // 2))


def action_for(scene):
    requested = str(scene.get("motion", "")).lower()
    action = str(scene.get("action", "") if requested in ("", "auto") else requested).lower()
    rules = [
        (("run", "sprint", "chase", "escape", "dash"), "run"),
        (("sneak", "tiptoe", "creep", "quietly"), "sneak"),
        (("panic", "terrified", "freeze", "surprised", "shocked", "confused", "caught"), "panic"),
        (("point", "explain", "reveal", "brief", "map", "signal"), "point"),
        (("wave", "hello", "greet"), "wave"),
        (("celebrate", "victory", "cheer", "success"), "celebrate"),
        (("fall", "trip", "slip", "stumble"), "fall"),
        (("surrender", "hands up", "arrest"), "surrender"),
        (("aim", "guard", "watch"), "aim"),
    ]
    for words, result in rules:
        if any(word in action for word in words):
            return result
    return "idle"


def draw_speech_bubble(draw, text, x, y, max_width):
    lines = wrap_words(text, max(14, int(max_width / max(1, H * .017))))
    fnt = font(int(H * .020), True)
    line_h = int(H * .027)
    lines = lines[:3]
    width = min(max_width, max([draw.textbbox((0, 0), line, font=fnt)[2] for line in lines] + [int(H * .12)]) + int(H * .04))
    height = line_h * len(lines) + int(H * .025)
    x0 = int(clamp(x - width / 2, W * .03, W * .97 - width))
    y0 = int(clamp(y, H * .10, H * .54))
    draw.rounded_rectangle((x0, y0, x0 + width, y0 + height), radius=14, fill=(250, 250, 245, 242), outline=(20, 28, 39, 255), width=3)
    for i, line in enumerate(lines):
        centered(draw, (x0 + width / 2, y0 + int(H * .012) + line_h * (i + .5)), line, fnt, "#182230")
    draw.polygon([(x - 9, y0 + height - 2), (x + 9, y0 + height - 2), (x, y0 + height + 12)], fill=(250, 250, 245, 242), outline=(20, 28, 39, 255))


def synth_music(seconds):
    n = int(SR * seconds)
    t = np.arange(n, dtype=np.float32) / SR
    # Original royalty-free-by-construction procedural bed: no downloaded track.
    chord = np.sin(2 * np.pi * 55 * t) + .55 * np.sin(2 * np.pi * 82.41 * t) + .32 * np.sin(2 * np.pi * 110 * t)
    pulse = .52 + .48 * (np.sin(2 * np.pi * .72 * t) ** 2)
    music = chord * pulse * .045
    # Soft high note every four beats adds movement without harsh clicks.
    note = np.maximum(0, np.sin(2 * np.pi * .25 * t)) ** 10
    music += np.sin(2 * np.pi * 440 * t) * note * .012
    return np.clip(music, -1, 1).astype(np.float32)


def synth_sfx(kind, seconds=.24):
    n = max(1, int(SR * seconds))
    t = np.arange(n, dtype=np.float32) / SR
    envelope = np.exp(-t * (7 if kind == "impact" else 4))
    if kind == "beep":
        signal = np.sin(2 * np.pi * (660 + 180 * np.sin(2 * np.pi * 3 * t)) * t)
    elif kind == "impact":
        signal = np.sin(2 * np.pi * (90 + 35 * np.sin(2 * np.pi * 18 * t)) * t)
    elif kind == "alarm":
        signal = np.sin(2 * np.pi * (540 + 260 * np.sin(2 * np.pi * 2 * t)) * t)
    else:
        signal = np.random.default_rng(17).normal(0, .5, n)
    return (signal * envelope * .12).astype(np.float32)


def synth_kokoro(pipeline, text, voice_name="af_heart", speed=1.04):
    """Generate natural English narration with the same Kokoro voice family as manga-video-maker."""
    import re
    sentences = [s.strip() for s in re.split(r"(?<=[,.!?])\s+", str(text).strip()) if s.strip()]
    if not sentences:
        raise RuntimeError("Kokoro received empty narration text.")
    pieces = []
    for sentence in sentences:
        sentence_audio = []
        for _, _, audio in pipeline(sentence, voice=voice_name, speed=float(speed)):
            if audio is not None:
                arr = audio.detach().cpu().numpy() if hasattr(audio, "detach") else np.asarray(audio)
                sentence_audio.append(np.asarray(arr, dtype=np.float32).reshape(-1))
        if not sentence_audio:
            raise RuntimeError("Kokoro produced no audio for a narration sentence.")
        pieces.append(np.concatenate(sentence_audio))
        pause = 0.38 if sentence.endswith((".", "!", "?")) else 0.18
        pieces.append(np.zeros(int(24000 * pause), dtype=np.float32))
    audio = np.concatenate(pieces)
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak < 0.001:
        raise RuntimeError("Kokoro generated silent narration.")
    if peak > 0.95:
        audio *= 0.95 / peak
    # Kokoro emits 24 kHz; resample to the renderer's 22.05 kHz mix rate.
    new_len = max(1, int(len(audio) * SR / 24000))
    audio = np.interp(np.linspace(0, len(audio) - 1, new_len), np.arange(len(audio)), audio).astype(np.float32)
    return audio


def read_wav(path):
    with wave.open(str(path), "rb") as w:
        channels, width, rate = w.getnchannels(), w.getsampwidth(), w.getframerate()
        raw = w.readframes(w.getnframes())
    if width != 2:
        raise ValueError("Expected 16-bit PCM audio")
    arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768
    if channels > 1:
        arr = arr.reshape(-1, channels).mean(axis=1)
    if rate != SR and len(arr):
        new_len = max(1, int(len(arr) * SR / rate))
        arr = np.interp(np.linspace(0, len(arr) - 1, new_len), np.arange(len(arr)), arr).astype(np.float32)
    return arr


def audio_track(scenes, total_seconds):
    TMP.mkdir(parents=True, exist_ok=True)
    total_n = int(total_seconds * SR)
    voice = np.zeros(total_n, dtype=np.float32)
    sfx = np.zeros(total_n, dtype=np.float32)
    cursor = 0.0
    voice_windows = []
    voice_name = os.getenv("VOICE_NAME", "af_heart")
    pipeline = None
    if VOICE_ON:
        try:
            from kokoro import KPipeline
            pipeline = KPipeline(lang_code="a")
            print(f"NARRATION_ENGINE=Kokoro; voice={voice_name}; speed=1.04")
        except Exception as exc:
            raise RuntimeError(f"Kokoro voice engine could not initialize: {exc}") from exc
    for i, scene in enumerate(scenes):
        slot = float(scene["duration"])
        dialogue = str(scene.get("dialogue") or scene.get("narration") or scene.get("action", ""))
        start = int((cursor + min(.45, slot * .06)) * SR)
        available = max(1, int(max(.5, slot - .8) * SR))
        if VOICE_ON and dialogue:
            # Strip speaker labels so the selected narrator reads the dialogue naturally.
            import re
            spoken_text = re.sub(r"(?i)\b(?:planner|rookie|pixel|captain\s+vale):\s*", " ", dialogue)
            clip = synth_kokoro(pipeline, spoken_text, voice_name=voice_name, speed=1.04)
            if len(clip) > available:
                # Keep narration inside its scene slot; this is a rare safety limit for long dialogue.
                clip = np.interp(np.linspace(0, len(clip) - 1, available), np.arange(len(clip)), clip).astype(np.float32)
            end = min(total_n, start + len(clip))
            if end > start:
                voice[start:end] += clip[:end - start] * .62
                voice_windows.append((start, end))
        action_text = (str(scene.get("action", "")) + " " + str(scene.get("sfx", ""))).lower()
        kind = "alarm" if any(k in action_text for k in ("alarm", "sirens", "siren")) else ("beep" if any(k in action_text for k in ("beep", "button", "keypad", "doorbell")) else ("impact" if any(k in action_text for k in ("crash", "slam", "fall", "bang", "thud")) else None))
        if kind:
            fx = synth_sfx(kind, .45 if kind == "alarm" else .22)
            at = min(total_n, int((cursor + slot * .72) * SR))
            end = min(total_n, at + len(fx))
            if end > at:
                sfx[at:end] += fx[:end - at]
        cursor += slot
    music = synth_music(total_seconds)
    # Side-chain ducking: reduce music while narration is present.
    duck = np.ones(total_n, dtype=np.float32)
    # Smooth duck edges with short ramps; avoid a costly full-track convolution.
    fade = max(1, int(.10 * SR))
    for start, end in voice_windows:
        left = max(0, start - int(.18 * SR))
        right = min(total_n, end + int(.28 * SR))
        if right <= left:
            continue
        duck[left:right] = .28
        ramp_in_end = min(right, left + fade)
        ramp_out_start = max(left, right - fade)
        if ramp_in_end > left:
            duck[left:ramp_in_end] = np.linspace(1.0, .28, ramp_in_end - left, dtype=np.float32)
        if right > ramp_out_start:
            duck[ramp_out_start:right] = np.linspace(.28, 1.0, right - ramp_out_start, dtype=np.float32)
    mixed = np.clip(voice[:total_n] + sfx[:total_n] + music[:total_n] * duck, -.95, .95)
    path = TMP / "mix.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mixed * 32767).astype(np.int16).tobytes())
    return path


def build_scenes(data, target_seconds):
    source = data.get("scenes") or []
    if not source:
        raise ValueError("scripts/episode.json needs at least one scene")
    scenes, remaining, index = [], float(target_seconds), 0
    while remaining > .001:
        base = source[index % len(source)]
        duration = min(float(base.get("duration", 10)), remaining)
        if duration <= 0:
            raise ValueError(f"Scene {index + 1} duration must be positive")
        scenes.append({**base, "duration": duration, "scene_number": index + 1})
        remaining -= duration
        index += 1
    return scenes


def draw_overlay(im, data, scene, scene_index, scene_time, scene_count, accent, character_map):
    d = ImageDraw.Draw(im, "RGBA")
    # Cinematic clean frame: no persistent scene counters or title HUD.
    bar = int(H * .018)
    d.rectangle((0, 0, W, bar), fill=(0, 0, 0, 85))
    d.rectangle((0, H - bar, W, H), fill=(0, 0, 0, 95))
    # Light camera shake on action beats and slow digital push-in.
    motion = action_for(scene)
    if motion in ("run", "fall") and int(scene_time * 12) % 2:
        d.rectangle((0, bar, W, H - bar), outline=(255, 230, 180, 35), width=8)
    # Cinematic staging: vary screen position and scale by beat instead of placing
    # every cast member in a static lineup. Character identity remains stable.
    ids = [cid for cid in scene.get("characters", []) if cid in character_map]
    ids = ids or list(character_map)[:2]
    ids = ids[:3]
    ground = int(H * (.72 if motion in ("fall", "run") else .73))
    travel = scene_time / max(.1, float(scene["duration"]))
    if len(ids) == 1:
        positions = [W * (.50 + .025 * math.sin(travel * math.pi * 2))]
    elif len(ids) == 2:
        positions = [W * .34, W * .66]
    else:
        positions = [W * .23, W * .50, W * .77]
    for slot, (cid, xpos) in enumerate(zip(ids, positions)):
        c = character_map[cid]
        direction = 1 if slot == 0 else -1
        phase = scene_time * (6.5 if motion == "run" else 3.0)
        shift = 0
        if motion in ("run", "dash"):
            shift = int(math.sin(phase + slot * 1.8) * W * .045)
        elif motion == "sneak":
            shift = int(math.sin(phase + slot) * W * .018)
        elif motion == "fall":
            shift = int(math.sin(scene_time * 4 + slot) * W * .025)
        emphasis = 1.16 if motion in ("panic", "react", "surrender", "celebrate", "fall") else 1.0
        push = emphasis + .035 * math.sin(travel * math.pi)
        x = int(xpos + shift)
        draw_character(d, c, x, ground, scene_time + slot * .6, scale=push, action=motion,
                       facing=direction, accent=accent, name_tag=False)
    # Minimal editorial captions: remove the oversized boxed banner that made
    # every frame look like a template. Short hook text gets a subtle shadow.
    caption = str(scene.get("caption") or "")
    if caption:
        lines = wrap_words(caption, max(18, int(W / 30)))[:2]
        fnt = font(int(H * .030), True)
        line_h = int(H * .038)
        py = int(H * .855)
        for li, line in enumerate(lines):
            words = line.split()
            widths = [d.textlength(word + " ", font=fnt) for word in words]
            x = (W - sum(widths)) / 2
            y = py + line_h * (li + .5)
            for wi, word in enumerate(words):
                fill = "#ff4d5a" if word.strip(".,!?").upper() in {"PLAN", "TRAP", "RUN", "ALARM", "WAIT", "NOW", "NO", "ESCAPE", "CAUGHT", "PERFECT", "IMPOSSIBLE"} else "#ffffff"
                d.text((x + 2, y + 3), word + " ", font=fnt, fill=(0, 0, 0, 190), anchor="lm", stroke_width=2, stroke_fill=(0, 0, 0, 210))
                d.text((x, y), word + " ", font=fnt, fill=fill, anchor="lm", stroke_width=1, stroke_fill="#111111")
                x += widths[wi]
    # Scene transition wipe/flash only at the very beginning/end of each scene.
    if scene_time < .18:
        alpha = int(150 * (1 - scene_time / .18))
        d.rectangle((0, bar, W, H - bar), fill=(0, 0, 0, alpha))
    return im


def render(data, scenes, audio_path):
    OUT.mkdir(exist_ok=True)
    TMP.mkdir(exist_ok=True)
    total = sum(float(s["duration"]) for s in scenes)
    output = OUT / "stickman-episode.mp4"
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-i", str(audio_path), "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-preset", "ultrafast" if W == 1280 else "veryfast",
        "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(output)
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    character_map = {c["id"]: c for c in data.get("characters", [])}
    if not character_map:
        proc.kill()
        raise ValueError("Add at least one character to scripts/episode.json")
    backgrounds = {}
    try:
        for si, scene in enumerate(scenes):
            setting = scene.get("setting", "safehouse")
            if setting not in backgrounds:
                backgrounds[setting] = make_background(setting)
            base, accent = backgrounds[setting]
            frames = max(1, int(round(float(scene["duration"]) * FPS)))
            for fi in range(frames):
                scene_time = fi / FPS
                im = base.copy()
                draw_overlay(im, data, scene, si, scene_time, len(scenes), accent, character_map)
                proc.stdin.write(im.convert("RGB").tobytes())
        proc.stdin.close()
        code = proc.wait()
        if code:
            raise RuntimeError(f"ffmpeg exited with code {code}")
    except Exception:
        if proc.stdin and not proc.stdin.closed:
            proc.stdin.close()
        proc.kill()
        raise
    if not output.exists() or output.stat().st_size < 10000:
        raise RuntimeError("MP4 output missing or unexpectedly small")
    print(f"Rendered: {output} ({output.stat().st_size:,} bytes, {total:.1f}s, {W}x{H}@{FPS})")


def srt_timestamp(seconds):
    milliseconds = int(round(max(0.0, seconds) * 1000))
    hours, rem = divmod(milliseconds, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    whole_seconds, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{ms:03d}"


def write_srt(scenes):
    """Export scene-timed captions as a phone-editable SRT sidecar."""
    OUT.mkdir(parents=True, exist_ok=True)
    cursor = 0.0
    entries = []
    for index, scene in enumerate(scenes, 1):
        start = cursor
        end = cursor + float(scene["duration"])
        caption = str(scene.get("caption") or scene.get("action", "")).strip()
        if caption:
            entries.extend([str(index), f"{srt_timestamp(start)} --> {srt_timestamp(end)}", caption, ""])
        cursor = end
    (OUT / "captions.srt").write_text("\n".join(entries), encoding="utf-8")
    print(f"Caption sidecar: {OUT / 'captions.srt'} ({len(entries) // 4} cues)")


def validate(data):
    if not isinstance(data.get("characters"), list) or not data["characters"]:
        raise ValueError("Episode needs a non-empty characters list")
    ids = {c.get("id") for c in data["characters"]}
    if None in ids or len(ids) != len(data["characters"]):
        raise ValueError("Every character needs a unique id")
    if not isinstance(data.get("scenes"), list) or not data["scenes"]:
        raise ValueError("Episode needs a non-empty scenes list")
    for i, scene in enumerate(data["scenes"], 1):
        if float(scene.get("duration", 10)) <= 0:
            raise ValueError(f"Scene {i} has a non-positive duration")
        if not (scene.get("action") or scene.get("narration") or scene.get("dialogue")):
            raise ValueError(f"Scene {i} needs action, narration, or dialogue")
        unknown = set(scene.get("characters", [])) - ids
        if unknown:
            raise ValueError(f"Scene {i} references unknown characters: {sorted(unknown)}")


def main():
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is required")
    with SCRIPT.open(encoding="utf-8") as f:
        data = json.load(f)
    validate(data)
    seconds = DURATION_MINUTES * 60
    scenes = build_scenes(data, seconds)
    print(f"Preparing {len(scenes)} scenes for {DURATION_MINUTES} minute(s) at {W}x{H}, {FPS} fps; character_color={COLOR_THEME}")
    write_srt(scenes)
    audio = audio_track(scenes, seconds)
    render(data, scenes, audio)
    shutil.rmtree(TMP, ignore_errors=True)
    print("Temporary audio files cleaned up.")


if __name__ == "__main__":
    main()
