"""Voice every line with Kokoro, build the soundtrack and timeline.json.
usage: python crime/voice.py ep.json outdir"""
import json, sys, numpy as np, soundfile as sf
from pathlib import Path
from kokoro import KPipeline
SR = 24000
ep = json.loads(Path(sys.argv[1]).read_text()); out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
pipes = {}
def tts(text, voice):
    lang = voice[0]
    if lang not in pipes: pipes[lang] = KPipeline(lang_code=lang)
    speed = 0.95 if voice == ep.get("narrator") else 1.0
    return np.concatenate([a.numpy() if hasattr(a, "numpy") else a for _, _, a in pipes[lang](text, voice=voice, speed=speed)])
voice, timeline, t = [], [], 0.0
for i, sh in enumerate(ep["shots"]):
    w = sh["line"]["who"]; v = ep["narrator"] if w == "nar" else ep["cast"][w]["voice"]
    a = tts(sh["line"]["text"], v); lead, tail = 0.25, 0.35
    seg = np.concatenate([np.zeros(int(lead*SR)), a, np.zeros(int(tail*SR))])
    timeline.append({"start": t, "dur": len(seg)/SR, "talk0": lead, "talk1": lead+len(a)/SR})
    voice.append(seg); t += len(seg)/SR
v = np.concatenate(voice).astype(np.float32); n = len(v); tt = np.arange(n)/SR
rng = np.random.default_rng(3)
# horror bed: detuned low drone, high eerie tone, heartbeat, wind
drone = 0.06*(np.sin(2*np.pi*55*tt)+np.sin(2*np.pi*55.7*tt)+0.6*np.sin(2*np.pi*82.4*tt))*(0.7+0.3*np.sin(2*np.pi*0.1*tt))
eerie = 0.012*np.sin(2*np.pi*(880+6*np.sin(2*np.pi*0.3*tt))*tt)*(0.5+0.5*np.sin(2*np.pi*0.05*tt))
noise = rng.standard_normal(n); k = 400; wind = np.convolve(noise, np.ones(k)/k, "same")*0.25*(0.6+0.4*np.sin(2*np.pi*0.07*tt))
beat = np.zeros(n)
for s in np.arange(0.5, n/SR, 1.1):
    for d, amp in ((0, 1), (0.22, 0.7)):
        j = int((s+d)*SR); m = min(n-j, int(0.18*SR))
        if m > 0: x = np.arange(m)/SR; beat[j:j+m] += amp*0.22*np.sin(2*np.pi*48*x)*np.exp(-x*22)
bed = drone+eerie+wind+beat
# stingers: thunder on lightning shots, low hit on the last shot
for sh, tl in zip(ep["shots"], timeline):
    if "lightning" in (sh.get("fx") or []):
        j = int((tl["start"]+1.2)*SR); m = min(n-j, int(2.5*SR)); x = np.arange(m)/SR
        bed[j:j+m] += np.convolve(rng.standard_normal(m), np.ones(60)/60, "same")*np.exp(-x*1.6)*1.2
    if sh.get("card"):
        j = int(tl["start"]*SR); m = min(n-j, int(2*SR)); x = np.arange(m)/SR
        bed[j:j+m] += 0.5*np.sin(2*np.pi*40*x)*np.exp(-x*2.5)
mix = v + 0.55*bed; mix /= max(1.0, np.abs(mix).max()/0.95)
sf.write(out/"audio.wav", mix.astype(np.float32), SR)
(out/"timeline.json").write_text(json.dumps(timeline)); print("total", round(t, 1), "s")
