"""Channel stats report (read-only): subscribers, views, and how each recent video performs."""
import re, sys
sys.path.insert(0, ".")
from pipeline.youtube_upload import _client
yt = _client()
ch = yt.channels().list(part="snippet,statistics,contentDetails", mine=True).execute()["items"][0]
s = ch["statistics"]
print(f'CHANNEL {ch["snippet"]["title"]}: subs={s.get("subscriberCount")} views={s["viewCount"]} videos={s["videoCount"]}')
up = ch["contentDetails"]["relatedPlaylists"]["uploads"]
ids, tok = [], None
while len(ids) < 150:
    r = yt.playlistItems().list(part="contentDetails", playlistId=up, maxResults=50, pageToken=tok).execute()
    ids += [i["contentDetails"]["videoId"] for i in r["items"]]
    tok = r.get("nextPageToken")
    if not tok: break
rows = []
for i in range(0, len(ids), 50):
    for v in yt.videos().list(part="snippet,statistics,contentDetails,status", id=",".join(ids[i:i+50])).execute()["items"]:
        d = re.findall(r"(\d+)([HMS])", v["contentDetails"]["duration"])
        sec = sum(int(n) * {"H": 3600, "M": 60, "S": 1}[u] for n, u in d)
        rows.append((v["snippet"]["publishedAt"][:10], sec, int(v["statistics"].get("viewCount", 0)),
                     int(v["statistics"].get("likeCount", 0)), v["status"]["privacyStatus"], v["snippet"]["title"][:70]))
longs = [r for r in rows if r[1] > 180]; shorts = [r for r in rows if r[1] <= 180]
for name, g in (("LONG", longs), ("SHORT", shorts)):
    if g:
        print(f"{name}: count={len(g)} total_views={sum(r[2] for r in g)} avg_views={sum(r[2] for r in g)//len(g)} avg_len_min={sum(r[1] for r in g)/len(g)/60:.1f}")
print("TOP 8 LONG:"); [print("  ", r) for r in sorted(longs, key=lambda r: -r[2])[:8]]
print("LATEST 12:"); [print("  ", r) for r in rows[:12]]
