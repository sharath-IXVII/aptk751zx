"""Voice every scene (free Edge TTS), time each scene to its narration, make a music bed.
  python voice.py <episode.json> <public_dir> <props_out.json>"""
import json, subprocess, sys, time
from pathlib import Path
ep_file, pub, props = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
ep = json.load(open(ep_file)); (pub / "audio").mkdir(parents=True, exist_ok=True)
FPS = 30
def dur(f):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
                                capture_output=True, text=True, check=True).stdout)
if not ep.get("short_scenes") and ep.get("short"):
    ep["short_scenes"] = [dict(ep["scenes"][i]) for i in ep["short"] if 0 <= i < len(ep["scenes"])] + [
        {"type": "lab-outro" if ep.get("style") == "lab" else "outro", "title": (ep.get("title") or "").upper()[:40], "lines": [],
         "cta": "Full video on our channel", "narration": "Watch the full video on our channel."}]
jobs = [(f"s{i}", s) for i, s in enumerate(ep["scenes"])] + [(f"sh{i}", s) for i, s in enumerate(ep.get("short_scenes", []))]
KOKORO = None
def kokoro_say(text, voice, speed, wav):
    """Kokoro: free, open-source voice that runs on this machine (default: af_heart)."""
    global KOKORO
    from kokoro import KPipeline
    import soundfile as sf, numpy as np
    if KOKORO is None:
        KOKORO = KPipeline(lang_code=voice[0])
    audio = np.concatenate([a for _, _, a in KOKORO(text, voice=voice, speed=speed)])
    sf.write(str(wav), audio, 24000)

engine = ep.get("engine", "kokoro")
for key, s in jobs:
    i = key
    f = pub / "audio" / f"{key}.mp3"
    if engine == "kokoro":
        wav = f.with_suffix(".wav")
        kokoro_say(s["narration"], ep.get("kokoro_voice", "af_heart"), float(ep.get("speed", 1.05)), wav)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-b:a", "160k", str(f)], check=True); wav.unlink()
    else:
      for attempt in range(8):
        v = ep.get("voice", "en-US-AndrewMultilingualNeural") if attempt < 5 else "en-US-GuyNeural"
        r = subprocess.run(["edge-tts", "--voice", v, f"--rate={ep.get('rate', '+4%')}", "--text", s["narration"], "--write-media", str(f)], capture_output=True, text=True)
        if r.returncode == 0 and f.exists() and f.stat().st_size > 2000:
            break
        print("voice retry", i, r.stderr[-150:]); time.sleep(3 * (attempt + 1))
    d = dur(f); s["audio"] = True; s["audio_key"] = key
    s["frames"] = int((d + (0.9 if s["type"] in ("title", "outro") else 0.3)) * FPS)
    print(f"scene {key:5s} {s['type']:9s} {d:5.1f}s")
total = sum(s["frames"] for s in ep["scenes"]) / FPS
json.dump({"ep": ep}, open(props, "w"))
json.dump({"ep": ep, "short": True}, open(props.replace(".json", "_short.json"), "w"))
# ---------------------------------------------------------------- music bed + sound effects (made here: no copyright)
import numpy as np
import soundfile as sf
SR = 48000
theme = (ep.get("theme") or "").split("-")[0]
def music(seconds):
    """Soft background bed. Lessons: calm major pad with a gentle pulse. News (ent): low tense pulse."""
    t = np.arange(int(seconds * SR)) / SR
    if theme == "ent":
        chords = [[110, 130.81, 164.81], [98, 116.54, 146.83], [87.31, 110, 130.81], [98, 123.47, 146.83]]
        bar = 4.0
    else:
        chords = [[130.81, 164.81, 196.0], [110, 130.81, 164.81], [87.31, 110, 130.81], [98, 123.47, 146.83]]
        bar = 4.0
    out = np.zeros_like(t)
    idx = (t // bar).astype(int) % len(chords)
    for k in range(3):
        f = np.array([c[k] for c in chords])[idx]
        out += 0.18 * np.sin(2 * np.pi * f * t) + 0.06 * np.sin(4 * np.pi * f * t)
    pulse = 0.55 + 0.45 * (0.5 + 0.5 * np.cos(2 * np.pi * t / (0.5 if theme == "ent" else 1.0)))
    out *= pulse
    fade = np.minimum(1, np.minimum(t / 3, (seconds - t) / 3)).clip(0, 1)
    return (out * fade * 0.5).astype(np.float32)

def tone(f, d, vol=0.5, decay=8.0):
    t = np.arange(int(d * SR)) / SR
    return (vol * np.sin(2 * np.pi * f * t) * np.exp(-decay * t)).astype(np.float32)

rng = np.random.default_rng(7)
def whoosh(d=0.45, vol=0.22):
    n = int(d * SR); x = rng.standard_normal(n).astype(np.float32)
    k = 40; x = np.convolve(x, np.ones(k) / k, mode="same")          # soften the noise
    env = np.sin(np.linspace(0, np.pi, n)) ** 2
    return (x * env * vol * 6).astype(np.float32)

def layer(*xs):
    n = max(len(x) for x in xs); out = np.zeros(n, dtype=np.float32)
    for x in xs: out[: len(x)] += x
    return out
SFX = {"whoosh": whoosh(), "tick": tone(1400, 0.07, 0.35, 60), "ding": layer(tone(1318.5, 0.7, 0.35, 5), tone(1760, 0.7, 0.2, 6)),
       "thump": layer(tone(70, 0.4, 0.6, 9), tone(140, 0.25, 0.3, 14)), "pop": tone(880, 0.12, 0.3, 30)}
def sfx_track(scenes, seconds, offset=0):
    track = np.zeros(int((seconds + 1) * SR), dtype=np.float32)
    def put(name, at):
        a = int(at * SR); x = SFX[name]; b = min(len(track), a + len(x))
        if 0 <= a < len(track): track[a:b] += x[: b - a]
    at = offset
    for i, sc in enumerate(scenes):
        d = sc["frames"] / FPS
        if i > 0: put("whoosh", max(0, at - 0.15))
        tp = sc.get("type")
        if tp == "question" and not sc.get("reveal"):
            for k in range(3): put("tick", at + d - (95 - 30 * k) / FPS)
        if tp == "question" and sc.get("reveal"): put("ding", at + 0.1)
        if tp == "stamp": put("thump", at + 0.15)
        if tp in ("steps", "phone"): put("pop", at + 0.3)
        at += d
    return track

def bed(scenes, path, offset=0):
    seconds = offset + sum(sc["frames"] for sc in scenes) / FPS
    m = music(seconds + 1); fx = sfx_track(scenes, seconds, offset)
    n = min(len(m), len(fx)); mix = m[:n] * 0.9 + fx[:n]
    mix = mix / max(1.0, float(np.abs(mix).max()) / 0.85)   # never clip
    sf.write(str(path), np.stack([mix, mix], axis=1), SR)

bed(ep["scenes"], pub / "music.wav")
if ep.get("short_scenes"):
    bed(ep["short_scenes"], pub / "music_short.wav")
print(f"total {total / 60:.1f} min")
