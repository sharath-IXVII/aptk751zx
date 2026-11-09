"""Instagram upload test WITHOUT posting: make a 10 s test clip, upload it both ways, wait for
Instagram to process it, print the result. Nothing is published (no media_publish call)."""
import os, subprocess, sys, time
sys.path.insert(0, ".")
from pathlib import Path
import httpx
from pipeline import social

src = Path("test_src.mp4")
subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=720x1280:rate=30",
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=24000", "-t", "10",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(src)], check=True)
ready = social._ig_ready(src)
print(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,width,height,sample_aspect_ratio,r_frame_rate,sample_rate,channels",
                      "-of", "compact", str(ready)], capture_output=True, text=True).stdout)
ig, token, G = os.environ["IG_USER_ID"], os.environ["IG_ACCESS_TOKEN"], social._ig_graph()
print("API:", G)

def wait(c):
    for _ in range(30):
        time.sleep(6)
        st = httpx.get(f"{G}/{c}", params={"fields": "status_code,status", "access_token": token}, timeout=30).json()
        if st.get("status_code") in ("FINISHED", "ERROR"):
            return st
    return st

# A) resumable upload
r = httpx.post(f"{G}/{ig}/media", timeout=60, data={"media_type": "REELS", "upload_type": "resumable",
               "caption": "test", "access_token": token})
print("A create:", r.status_code, r.text[:300])
if r.status_code == 200:
    j = r.json(); data = ready.read_bytes()
    for hdr in ({"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(len(data))},
                {"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(len(data)),
                 "Content-Type": "application/octet-stream"}):
        up = httpx.post(j["uri"], content=data, headers=hdr, timeout=300)
        print("A upload:", up.status_code, up.text[:300])
        if up.status_code == 200:
            break
    print("A status:", wait(j["id"]))

# B) video_url with the FINAL direct link (GitHub release links redirect; Instagram may not follow)
with social._PublicLink(ready) as url:
    final = str(httpx.head(url, follow_redirects=True, timeout=60).url)
    print("B link redirects:", url != final)
    for u in (final, url):
        r = httpx.post(f"{G}/{ig}/media", timeout=60, data={"media_type": "REELS", "video_url": u,
                       "caption": "test", "access_token": token})
        print("B create:", r.status_code, r.text[:200])
        if r.status_code == 200:
            print("B status (", "final link" if u == final else "github link", "):", wait(r.json()["id"]))

# C) REAL post (only when the workflow is run with "publish" ticked): proves the whole chain works.
if os.getenv("PUBLISH") == "true":
    r = httpx.post(f"{G}/{ig}/media", timeout=60, data={"media_type": "REELS", "upload_type": "resumable",
                   "caption": "Test post - checking our Reels upload works. Full videos on our YouTube channel!",
                   "share_to_feed": "true", "access_token": token})
    print("C create:", r.status_code, r.text[:300])
    j = r.json(); data = ready.read_bytes()
    up = httpx.post(j["uri"], content=data, timeout=300, headers={
        "Authorization": f"OAuth {token}", "offset": "0", "file_size": str(len(data))})
    print("C upload:", up.status_code, up.text[:200])
    print("C status:", wait(j["id"]))
    r = httpx.post(f"{G}/{ig}/media_publish", timeout=60, data={"creation_id": j["id"], "access_token": token})
    print("C publish:", r.status_code, r.text[:300])
    if r.status_code == 200:
        p = httpx.get(f"{G}/{r.json()['id']}", params={"fields": "permalink", "access_token": token}, timeout=30).json()
        print("REAL REEL POSTED:", p.get("permalink"))
    else:
        sys.exit(1)
