#!/usr/bin/env python3
"""Deterministic 2D stickman episode renderer. Runs in GitHub Actions without API keys."""
from __future__ import annotations
import json, math, os, random, shutil, subprocess, wave
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
TMP = ROOT / ".render_tmp"
SCRIPT = ROOT / "scripts" / "episode.json"
FPS = 24
W, H = (1920, 1080) if os.getenv("RESOLUTION", "720p") == "1080p" else (1280, 720)
DURATION_MINUTES = max(1, min(8, int(os.getenv("DURATION_MINUTES", "1"))))
VOICE_ON = os.getenv("VOICE", "on").lower() == "on"
random.seed(23)

def font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"
    ]
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def clamp(v, lo, hi): return max(lo, min(hi, v))
def color(hexstr):
    s = hexstr.lstrip("#")
    return tuple(int(s[i:i+2], 16) for i in (0, 2, 4))

def centered(draw, xy, text, fnt, fill, stroke_width=0, stroke_fill="#000000"):
    draw.text(xy, text, font=fnt, fill=fill, anchor="mm", stroke_width=stroke_width, stroke_fill=stroke_fill)

def wrap_words(text, max_chars=34):
    words, lines, line = str(text).split(), [], ""
    for word in words:
        if len(line) + len(word) + (1 if line else 0) > max_chars:
            lines.append(line); line = word
        else: line = (line + " " + word).strip()
    if line: lines.append(line)
    return lines

def background(scene, t, index):
    setting = scene.get("setting", "safehouse")
    palettes = {
        "safehouse": ("#202b3d", "#34455b", "#d8a45c"),
        "bank": ("#b9d8e8", "#e9eef0", "#d7a64a"),
        "street": ("#172a46", "#425b73", "#f2c14e"),
        "police": ("#1c2c3e", "#40556c", "#6dc5ff"),
        "warehouse": ("#34313b", "#5d5661", "#e0a458"),
        "roof": ("#26384b", "#6c8da4", "#f4c95d")
    }
    sky, floor, accent = palettes.get(setting, palettes["safehouse"])
    im = Image.new("RGB", (W, H), sky)
    d = ImageDraw.Draw(im)
    # Gradient sky
    top, bottom = color(sky), color(floor)
    for y in range(H):
        f = y / max(1, H-1)
        c = tuple(int(top[k]*(1-f)+bottom[k]*f) for k in range(3))
        d.line((0,y,W,y), fill=c)
    # Architectural silhouettes
    horizon = int(H*.70)
    if setting in ("street", "roof", "police"):
        bw = W//9
        for i in range(-1, 11):
            x = i*bw
            bh = int(H*(.18 + ((i*37)%7)/35))
            d.rectangle((x,horizon-bh,x+bw-8,horizon), fill="#253348", outline="#172333", width=max(2,W//500))
            for wy in range(horizon-bh+24, horizon-16, 35):
                for wx in range(x+15,x+bw-15,30):
                    d.rectangle((wx,wy,wx+9,wy+13), fill=accent)
    elif setting == "bank":
        d.rectangle((W*.12,H*.22,W*.88,horizon), fill="#e5e1d8", outline="#596575", width=5)
        for x in np.linspace(W*.18,W*.82,7):
            d.polygon([(x-18,H*.30),(x+18,H*.30),(x+24,horizon),(x-24,horizon)], fill="#f7f3e9", outline="#66717d")
        d.polygon([(W*.10,H*.23),(W*.5,H*.10),(W*.90,H*.23)], fill="#c9d0d7", outline="#66717d")
        centered(d,(W*.5,H*.18),"CITY BANK",font(int(H*.035),True),"#28364a")
    else:
        # Interior walls and ceiling lamps
        d.rectangle((W*.05,H*.12,W*.95,horizon), fill="#354252", outline="#111a27", width=4)
        d.line((W*.05,H*.28,W*.95,H*.28), fill="#566477", width=3)
        for x in (W*.22,W*.5,W*.78):
            d.ellipse((x-30,H*.14,x+30,H*.17), fill="#ffe7a6")
            d.line((x,H*.17,x,H*.27), fill="#8d9aa8", width=3)
        if setting == "safehouse":
            # planning board with map lines and pins
            bx,by,bw,bh = int(W*.58),int(H*.20),int(W*.32),int(H*.34)
            d.rounded_rectangle((bx,by,bx+bw,by+bh), radius=12, fill="#e4ddc9", outline="#151c26", width=5)
            for j in range(5):
                x1=bx+25+j*bw//5
                d.line((x1,by+25,x1+bw//6,by+bh-25), fill="#a5a18f", width=3)
            for j in range(4):
                y=by+35+j*bh//4
                d.line((bx+20,y,bx+bw-20,y+15), fill="#b0a894", width=3)
            for px,py in ((.66,.30),(.78,.39),(.84,.28),(.72,.47)):
                x,y=int(W*px),int(H*py)
                d.ellipse((x-9,y-9,x+9,y+9), fill="#cf4545", outline="#632b2b", width=2)
    # floor
    d.rectangle((0,horizon,W,H), fill="#252d3a")
    d.polygon([(0,horizon),(W,horizon),(W,H),(0,H)], fill="#303744")
    for x in range(0,W,120):
        d.line((W*.5,horizon,x,H), fill="#3b4552", width=2)
    d.line((0,horizon,W,horizon), fill="#111923", width=5)
    return im, accent

def draw_character(draw, c, x, ground, t, scale=1.0, action="idle", accent="#f2c14e"):
    # Stable identity comes from the character bible; animation changes pose only.
    head = int(H*.073*scale); torso = int(H*.19*scale); limb = int(H*.14*scale)
    bob = int(math.sin(t*5.5)*H*.008) if action in ("walk","run","sneak","react") else int(math.sin(t*2.3)*H*.003)
    y = ground + bob
    line = max(4, int(H*.009*scale))
    skin = c.get("accent", "#f0c6a2")
    outfit = c.get("outfit", "#c83c3c")
    dark = "#141923"
    # torso
    dline = draw.line
    shoulder_y = y - torso
    hip_y = y - int(torso*.30)
    dline((x, shoulder_y, x, hip_y), fill=outfit, width=max(line*4, 15), joint="curve")
    # jacket seams and zipper
    draw.line((x, shoulder_y+8, x, hip_y), fill="#f5c7c7", width=max(2,line//2))
    draw.line((x-line*2, shoulder_y+int(torso*.25), x+line*2, shoulder_y+int(torso*.25)), fill="#f3d0d0", width=max(2,line//2))
    # legs with deterministic walk cycle
    leg_phase = math.sin(t*7) * limb*.45 if action in ("walk","run","sneak") else 0
    if action == "run": leg_phase *= 1.5
    dline((x, hip_y, x-leg*.40+leg_phase, y+int(limb*.78)), fill=dark, width=line, joint="curve")
    dline((x, hip_y, x+leg*.40-leg_phase, y+int(limb*.78)), fill=dark, width=line, joint="curve")
    # shoes
    draw.line((x-leg*.40+leg_phase, y+int(limb*.78), x-leg*.40+leg_phase+line*2, y+int(limb*.78)), fill="#10141b", width=line)
    draw.line((x+leg*.40-leg_phase, y+int(limb*.78), x+leg*.40-leg_phase+line*2, y+int(limb*.78)), fill="#10141b", width=line)
    # arms: point, wave, react, idle
    arm_len = int(H*.12*scale)
    if action == "point":
        dline((x, shoulder_y+10, x+arm_len, shoulder_y-int(arm_len*.5)), fill=skin, width=line, joint="curve")
        dline((x, shoulder_y+10, x-arm_len*.65, shoulder_y+arm_len*.75), fill=skin, width=line, joint="curve")
    elif action in ("react","panic"):
        lift = int(arm_len*.75)
        dline((x, shoulder_y+10, x-arm_len*.75, shoulder_y-lift), fill=skin, width=line, joint="curve")
        dline((x, shoulder_y+10, x+arm_len*.75, shoulder_y-lift), fill=skin, width=line, joint="curve")
    elif action == "wave":
        dline((x, shoulder_y+10, x+arm_len*.45, shoulder_y-arm_len*.55), fill=skin, width=line, joint="curve")
        dline((x+arm_len*.45, shoulder_y-arm_len*.55, x+arm_len*.5+math.sin(t*9)*12, shoulder_y-arm_len*.95), fill=skin, width=line, joint="curve")
        dline((x, shoulder_y+10, x-arm_len*.65, shoulder_y+arm_len*.6), fill=skin, width=line, joint="curve")
    else:
        swing = int(math.sin(t*5)*arm_len*.12) if action in ("walk","run","sneak") else 0
        dline((x, shoulder_y+10, x-arm_len*.6+swing, shoulder_y+arm_len*.75), fill=skin, width=line, joint="curve")
        dline((x, shoulder_y+10, x+arm_len*.6-swing, shoulder_y+arm_len*.75), fill=skin, width=line, joint="curve")
    # head and hair
    hy = shoulder_y-head-int(H*.02)
    draw.ellipse((x-head,hy-head,x+head,hy+head), fill=skin, outline=dark, width=line)
    hair = c.get("hair","short")
    if hair == "messy":
        for i in range(7):
            hx = x-head+int(i*head/3)
            draw.polygon([(hx,hy-head//2),(hx+head//4,hy-head-int(head*.35)),(hx+head//2,hy-head//2)], fill="#16171b")
    elif hair == "neat":
        draw.pieslice((x-head,hy-head-int(head*.15),x+head,hy+head//2),180,355,fill="#1c2026")
    else:
        draw.pieslice((x-head,hy-head,x+head,hy+head//2),180,360,fill="#202126")
    # eyes, brows and mouth
    eye_y = hy-int(head*.04)
    eye_dx = int(head*.34)
    eye_r = max(3,int(head*.10))
    draw.ellipse((x-eye_dx-eye_r,eye_y-eye_r,x-eye_dx+eye_r,eye_y+eye_r),fill="#ffffff")
    draw.ellipse((x+eye_dx-eye_r,eye_y-eye_r,x+eye_dx+eye_r,eye_y+eye_r),fill="#ffffff")
    pupil = max(2,eye_r//2)
    draw.ellipse((x-eye_dx-pupil//2,eye_y-pupil//2,x-eye_dx+pupil,eye_y+pupil),fill=dark)
    draw.ellipse((x+eye_dx-pupil//2,eye_y-pupil//2,x+eye_dx+pupil,eye_y+pupil),fill=dark)
    if action in ("panic","react"):
        draw.arc((x-head//3,hy+head//4,x+head//3,hy+head*.72),0,180,fill=dark,width=max(2,line//2))
    else:
        draw.arc((x-head//3,hy+head//5,x+head//3,hy+head*.60),10,165,fill=dark,width=max(2,line//2))
    # tiny chest emblem, unique per character
    draw.ellipse((x-int(line*.9), shoulder_y+int(torso*.34), x+int(line*.9), shoulder_y+int(torso*.34)+int(line*1.8)), fill=accent, outline=dark, width=1)
    # character name tag
    centered(draw,(x, y+int(limb*.98)+int(H*.025)),c.get("name",c["id"]),font(max(13,int(H*.018)),True),"#ffffff",stroke_width=2)

def synth_music(path, seconds):
    sr=22050
    n=int(sr*seconds)
    # Low-volume original procedural suspense bed; no external music assets.
    t=np.arange(n,dtype=np.float32)/sr
    chord = (np.sin(2*np.pi*110*t)+.55*np.sin(2*np.pi*146.83*t)+.35*np.sin(2*np.pi*164.81*t))
    pulse=(.65+.35*np.sin(2*np.pi*.18*t))
    audio=np.clip(chord*pulse*.035,-1,1)
    pcm=(audio*32767).astype(np.int16)
    with wave.open(str(path),"wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm.tobytes())

def synth_voice(path, text, rate=155):
    exe=shutil.which("espeak-ng") or shutil.which("espeak")
    if not exe: return False
    subprocess.run([exe,"-s",str(rate),"-w",str(path),str(text)[:400]],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    return path.exists()

def audio_track(scenes, total_seconds):
    TMP.mkdir(parents=True,exist_ok=True)
    sr=22050
    voice=np.zeros(int(total_seconds*sr),dtype=np.float32)
    cursor=0.0
    if VOICE_ON:
        for i,scene in enumerate(scenes):
            line=scene.get("dialogue") or scene.get("action","")
            wavpath=TMP/f"voice_{i}.wav"
            if synth_voice(wavpath,line):
                with wave.open(str(wavpath),"rb") as w:
                    raw=w.readframes(w.getnframes())
                    a=np.frombuffer(raw,dtype=np.int16).astype(np.float32)/32768
                    if w.getnchannels()>1: a=a.reshape(-1,w.getnchannels()).mean(axis=1)
                start=int(cursor*sr); end=min(len(voice),start+len(a))
                if end>start: voice[start:end]+=a[:end-start]*.72
            cursor+=float(scene["duration"])
    musicpath=TMP/"music.wav"
    synth_music(musicpath,total_seconds)
    with wave.open(str(musicpath),"rb") as w:
        music=np.frombuffer(w.readframes(w.getnframes()),dtype=np.int16).astype(np.float32)/32768
    n=min(len(voice),len(music))
    mixed=np.clip(voice[:n]+music[:n],-.98,.98)
    with wave.open(str(TMP/"mix.wav"),"wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes((mixed*32767).astype(np.int16).tobytes())
    return TMP/"mix.wav"

def build_scenes(data, target_seconds):
    source=data.get("scenes") or []
    if not source: raise ValueError("scripts/episode.json needs at least one scene")
    scenes=[]
    remaining=target_seconds
    i=0
    while remaining>0:
        base=source[i%len(source)]
        duration=min(float(base.get("duration",8)),remaining)
        scenes.append({**base,"duration":duration})
        remaining-=duration; i+=1
    return scenes

def render(data, scenes, audio_path):
    OUT.mkdir(exist_ok=True)
    TMP.mkdir(exist_ok=True)
    total=sum(s["duration"] for s in scenes)
    output=OUT/"stickman-episode.mp4"
    cmd=["ffmpeg","-y","-loglevel","error","-f","rawvideo","-pix_fmt","rgb24","-s",f"{W}x{H}","-r",str(FPS),"-i","-","-i",str(audio_path),"-c:v","libx264","-preset","ultrafast" if W==1280 else "veryfast","-crf","20","-pix_fmt","yuv420p","-c:a","aac","-b:a","160k","-shortest","-movflags","+faststart",str(output)]
    proc=subprocess.Popen(cmd,stdin=subprocess.PIPE)
    global_index=0
    charmap={c["id"]:c for c in data.get("characters",[])}
    if not charmap: raise ValueError("Add at least one character to scripts/episode.json")
    try:
        for si,scene in enumerate(scenes):
            scene_frames=max(1,int(scene["duration"]*FPS))
            ids=[cid for cid in scene.get("characters",[]) if cid in charmap] or list(charmap)[:2]
            for fi in range(scene_frames):
                t=fi/FPS
                im,accent=background(scene,t,si)
                d=ImageDraw.Draw(im,"RGBA")
                # Gentle camera push-in simulation through animated edge vignette/letterbox.
                bar=int(H*.045)
                d.rectangle((0,0,W,bar),fill=(0,0,0,155))
                d.rectangle((0,H-bar,W,H),fill=(0,0,0,155))
                centered(d,(W*.5,bar*.48),str(data.get("title","Stickman Story")).upper(),font(int(H*.024),True),"#ffffff")
                # Subtle cinematic side lighting
                for k in range(5):
                    alpha=max(0,24-k*4)
                    d.rectangle((k*3,bar,W-k*3,H-bar),outline=(255,220,170,alpha),width=3)
                # Character positions are stable by slot; small movement gives each shot life.
                ground=int(H*.70)
                positions=np.linspace(W*.30,W*.70,len(ids))
                action_text=(scene.get("action","")).lower()
                act="idle"
                if any(word in action_text for word in ("walk","sneak","run","approach")): act="sneak" if "sneak" in action_text else ("run" if "run" in action_text else "walk")
                if any(word in action_text for word in ("point","map","reveal","explain")): act="point"
                if any(word in action_text for word in ("panic","freeze","disbelief","confused","upside down")): act="react"
                if any(word in action_text for word in ("wave","waves","waving")): act="wave"
                # slight push-in by varying character scale within each shot
                scale=1.0+0.035*math.sin(t*1.2)
                for slot,(cid,x) in enumerate(zip(ids,positions)):
                    x=int(x + math.sin(t*1.3+slot)*W*.008)
                    draw_character(d,charmap[cid],x,ground,t,scale=scale,action=act if slot==0 else ("react" if act=="point" else act),accent=accent)
                # Caption panel with legible white text and red highlight strip.
                caption=str(scene.get("caption") or scene.get("action",""))
                lines=wrap_words(caption.upper(),max(22,int(W/27)))
                f=font(int(H*.035),True)
                line_h=int(H*.047)
                panel_h=line_h*len(lines)+int(H*.045)
                py=int(H*.82)
                d.rounded_rectangle((W*.07,py,W*.93,min(H-bar,py+panel_h)),radius=18,fill=(8,12,20,220),outline=(255,255,255,110),width=2)
                d.rounded_rectangle((W*.07,py,W*.078, min(H-bar,py+panel_h)),radius=4,fill="#d94242")
                for li,line in enumerate(lines[:3]):
                    centered(d,(W*.5,py+int(H*.025)+line_h*(li+.5)),line,f,"#ffffff",stroke_width=1,stroke_fill="#101010")
                # Occasional tiny motion accents; avoid flashing.
                if act in ("run","panic") and fi%12<6:
                    d.line((W*.12,H*.62,W*.16,H*.60),fill="#f4c95d",width=4)
                proc.stdin.write(im.convert("RGB").tobytes())
                global_index+=1
        proc.stdin.close()
        code=proc.wait()
        if code: raise RuntimeError(f"ffmpeg exited with code {code}")
    except Exception:
        if proc.stdin and not proc.stdin.closed:
            proc.stdin.close()
        proc.kill()
        raise
    if not output.exists() or output.stat().st_size < 10000:
        raise RuntimeError("MP4 output missing or unexpectedly small")
    print(f"Rendered: {output} ({output.stat().st_size:,} bytes, {total:.1f}s, {W}x{H}@{FPS})")

def main():
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is required")
    with SCRIPT.open(encoding="utf-8") as f: data=json.load(f)
    seconds=DURATION_MINUTES*60
    scenes=build_scenes(data,seconds)
    audio=audio_track(scenes,seconds)
    render(data,scenes,audio)

if __name__=="__main__":
    main()
