"""Health check: which YouTube channel we upload to, its latest uploads, and the Instagram token."""
import os, sys
sys.path.insert(0, ".")
import httpx

print("=== YouTube")
try:
    from pipeline.youtube_upload import _client
    yt = _client()
    ch = yt.channels().list(part="snippet,contentDetails", mine=True).execute()["items"][0]
    print("Channel:", ch["snippet"]["title"])
    up = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    items = yt.playlistItems().list(part="contentDetails", playlistId=up, maxResults=12).execute()["items"]
    ids = [i["contentDetails"]["videoId"] for i in items]
    for v in yt.videos().list(part="snippet,status", id=",".join(ids)).execute()["items"]:
        s = v["status"]
        print(f'  {v["snippet"]["publishedAt"][:16]}  {s["privacyStatus"]:8} publishAt={s.get("publishAt","-")[:16]}  {s.get("uploadStatus")}  {v["snippet"]["title"][:60]}')
except Exception as e:
    print("YouTube check failed:", str(e)[:400])

print("=== Instagram")
t = (os.getenv("IG_ACCESS_TOKEN") or "").strip()
u = (os.getenv("IG_USER_ID") or "").strip()
print(f"token: starts with {t[:4]!r}, length {len(t)}, has spaces/newlines: {any(c.isspace() for c in os.getenv('IG_ACCESS_TOKEN') or '')}")
print(f"IG_USER_ID length {len(u)}, digits only: {u.isdigit()}")
if t:
    r = httpx.get("https://graph.instagram.com/v21.0/me", params={"fields": "user_id,username", "access_token": t}, timeout=30)
    print("Instagram says:", r.status_code, r.text[:300])
    if r.status_code == 200:
        print("IG_USER_ID matches the token's account:", r.json().get("user_id") == u)
