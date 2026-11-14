"""Build episodes from hand-written scripts in crime/scripts/<case>.txt.

python -m pipeline.crime_scripts            # (re)build every script, append new keys to order.json

Script format (one shot per line, '#' comments):
  CAST id | Name | m/f | look | hair | beard
  PART                                   (starts the next part)
  set frame who:act,who:act > speaker: text [TITLE]
frames: two solo face three bed grave court cell walk establish  (see crime_writer.place)
The last line of each part is the viewers' question (end card)."""
import json, re, sys
from pathlib import Path
sys.path.insert(0, "crime")
from pipeline import crime_writer as W

SCRIPTS = Path("crime/scripts")


def cast_from(lines, cid):
    cast, used = {}, {"m": 0, "f": 0}
    for ln in lines:
        p = [x.strip() for x in ln[4:].split("|")]
        i, name, g, look, hair = p[:5]; beard = len(p) > 5 and p[5] == "beard"
        cl, cl2 = W.CLOTH.get(look, W.CLOTH["plain"])
        if g == "f" and look in ("plain", "rich", "worker"): cl = W.FEM_CLOTH[W.h(i) % len(W.FEM_CLOTH)]; cl2 = cl
        spec = {"name": name, "skin": W.SKIN[W.h(i + cid) % len(W.SKIN)], "cloth": cl, "cloth2": cl2,
                "hair": W.HAIR.get(hair, "#4a3020"), "voice": W.VOICES[g][used[g] % len(W.VOICES[g])]}
        used[g] += 1
        if g == "f": spec["long"] = True
        if beard: spec["beard"] = True
        if look == "police": spec["cap"] = True
        if look == "detective": spec.update(coat=True, hat=True)
        if look in ("doctor", "judge"): spec["glasses"] = True
        if look == "nurse": spec["nurse"] = True
        cast[i] = spec
    return cast


LINE = re.compile(r"^(\w+)\s+(\w+)\s*([^>]*)>\s*(\w+)\s*:\s*(.+?)\s*(?:\[(.+)\])?$")


def parse_part(lines):
    shots = []
    for ln in lines:
        m = LINE.match(ln)
        if not m: raise ValueError(f"bad line: {ln}")
        st, fr, who, spk, text, title = m.groups()
        ids, acts = [], {}
        for w in [x.strip() for x in who.split(",") if x.strip()]:
            i, _, a = w.partition(":"); ids.append(i)
            if a: acts[i] = a
        s = {"set": st, "frame": fr, "who": ids, "acts": acts, "speaker": spk, "text": text}
        if title: s["title"] = title
        shots.append(s)
    return {"shots": shots}


def build(path: Path):
    cid = path.stem; case = next(c for c in W.ALL if c["id"] == cid)
    lines = [l.strip() for l in path.read_text().splitlines() if l.strip() and not l.strip().startswith("#")]
    cast = cast_from([l for l in lines if l.startswith("CAST ")], cid)
    parts, cur = [], None
    for l in lines:
        if l.startswith("CAST "): continue
        if l == "PART": cur = []; parts.append(cur); continue
        cur.append(l)
    assert len(parts) == len(case["parts"]), f"{cid}: {len(parts)} parts written, library has {len(case['parts'])}"
    W.present = lambda case, k, cast: list(cast)  # hand-written: every listed character is allowed
    keys = []
    for k, pl in enumerate(parts, 1):
        d = parse_part(pl); d["title"] = TITLES.get((cid, k)) or case["name"].title()
        ep = W.convert(case, k, cast, d)
        missing = {c["id"] for s in ep["shots"] for c in s.get("chars", [])} - set(cast)
        assert not missing, f"{cid} part {k}: unknown characters {missing}"
        (W.EP / f"{ep['key']}.json").write_text(json.dumps(ep, indent=1, ensure_ascii=False)); keys.append(ep["key"])
    return keys


TITLES = {}


def main():
    order = json.loads((W.EP / "order.json").read_text())
    for p in sorted(SCRIPTS.glob("*.txt"), key=lambda p: [c["id"] for c in W.ALL].index(p.stem)):
        for line in p.read_text().splitlines():
            m = re.match(r"#\s*TITLE\s+(\d+)\s*:\s*(.+)", line)
            if m: TITLES[(p.stem, int(m.group(1)))] = m.group(2).strip()
        for k in build(p):
            if k not in order: order.append(k)
        print("built", p.stem)
    (W.EP / "order.json").write_text(json.dumps(order, indent=1))
    print(len(order), "parts in the queue")


if __name__ == "__main__":
    main()
