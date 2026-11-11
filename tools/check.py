"""Health check: tests everything the robot needs and ends with a clear PASS / FAIL list.
The run turns red if anything is broken. Nothing is published anywhere."""
import datetime as dt
import os
import sys

sys.path.insert(0, ".")
import httpx

G = "https://graph.facebook.com/v21.0"
results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(("PASS  " if ok else "FAIL  ") + name + (f"  - {detail}" if detail else ""))


# ---------- Secrets
print("=== Secrets")
for s in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN", "IG_USER_ID", "IG_ACCESS_TOKEN",
          "NVIDIA_API_KEY", "NOTEBOOKLM_MASTER_TOKEN", "NOTEBOOKLM_AUTH_JSON"):
    check(f"secret {s} is set", bool((os.getenv(s) or "").strip()))

# ---------- YouTube
print("=== YouTube")
try:
    from pipeline.youtube_upload import _client
    yt = _client()
    ch = yt.channels().list(part="snippet,contentDetails", mine=True).execute()["items"][0]
    check("YouTube login works", True, ch["snippet"]["title"])
    up = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    items = yt.playlistItems().list(part="contentDetails", playlistId=up, maxResults=15).execute()["items"]
    ids = [i["contentDetails"]["videoId"] for i in items]
    vids = yt.videos().list(part="snippet,status", id=",".join(ids)).execute()["items"] if ids else []
    now = dt.datetime.now(dt.timezone.utc)
    bad, recent, upcoming = [], 0, 0
    for v in vids:
        s = v["status"]
        print(f'  {v["snippet"]["publishedAt"][:16]}  {s["privacyStatus"]:8} '
              f'publishAt={s.get("publishAt", "-")[:16]}  {s.get("uploadStatus")}  {v["snippet"]["title"][:60]}')
        if s.get("uploadStatus") in ("failed", "rejected"):
            bad.append(v["snippet"]["title"][:40])
        if now - dt.datetime.fromisoformat(v["snippet"]["publishedAt"].replace("Z", "+00:00")) < dt.timedelta(hours=48):
            recent += 1
        if s.get("publishAt") and dt.datetime.fromisoformat(s["publishAt"].replace("Z", "+00:00")) > now:
            upcoming += 1
    check("No failed or rejected YouTube uploads", not bad, ", ".join(bad))
    check("New YouTube uploads in the last 48 hours", recent > 0, f"{recent} uploads, {upcoming} scheduled ahead")
except Exception as e:
    check("YouTube login works", False, str(e)[:300])

# ---------- Instagram
print("=== Instagram")
t = (os.getenv("IG_ACCESS_TOKEN") or "").strip().strip('"').strip("'")
u = (os.getenv("IG_USER_ID") or "").strip().strip('"').strip("'")
if t and u:
    graph = G if t.startswith("EAA") else "https://graph.instagram.com/v21.0"
    r = httpx.get(f"{graph}/{u}", params={"fields": "username", "access_token": t}, timeout=30)
    check("Instagram account readable", r.status_code == 200,
          r.json().get("username", "") if r.status_code == 200 else r.text[:300])
    if t.startswith("EAA"):
        r = httpx.get(f"{G}/debug_token", params={"input_token": t, "access_token": t}, timeout=30)
        d = r.json().get("data", {}) if r.status_code == 200 else {}
        check("Instagram token valid", bool(d.get("is_valid")), "never expires" if d.get("expires_at") == 0 else str(d)[:200])
        check("Token has posting permission", "instagram_content_publish" in d.get("scopes", []))
    # The real test: ask Instagram to start a Reel upload (it is never uploaded or published).
    # This fails with "missing permissions" when the System User can't post to this account.
    r = httpx.post(f"{graph}/{u}/media", timeout=60, data={
        "media_type": "REELS", "upload_type": "resumable", "caption": "health check (not posted)",
        "access_token": t})
    check("Instagram allows posting Reels to this account", r.status_code == 200,
          "" if r.status_code == 200 else r.text[:300])

# ---------- Daily video runs (a stuck channel shows up here first)
print("=== Daily video runs")
repo, gh = os.getenv("GITHUB_REPOSITORY"), os.getenv("GH_TOKEN")
if repo and gh:
    try:
        r = httpx.get(f"https://api.github.com/repos/{repo}/actions/workflows/daily.yml/runs",
                      params={"per_page": 30, "status": "completed"}, timeout=30,
                      headers={"Authorization": f"Bearer {gh}", "Accept": "application/vnd.github+json"})
        r.raise_for_status()
        runs = [x for x in r.json()["workflow_runs"] if x["conclusion"] in ("success", "failure")]
        streak = 0
        for x in runs:  # newest first
            if x["conclusion"] != "failure":
                break
            streak += 1
        fails = sum(x["conclusion"] == "failure" for x in runs)
        check("Daily video is not stuck (fewer than 3 failures in a row)", streak < 3,
              f"{streak} failed runs in a row - open the latest failed run for the error")
        print(f"  last {len(runs)} runs: {fails} failed")
    except Exception as e:
        print("Could not read the Daily video runs:", str(e)[:200])

# ---------- Summary
failed = [n for n, ok, _ in results if not ok]
print("\n========== SUMMARY ==========")
for n, ok, d in results:
    print(("  OK    " if ok else "  BROKEN ") + n + (f"  ({d})" if d and not ok else ""))
print("ALL GOOD" if not failed else f"{len(failed)} PROBLEM(S) - see MAINTENANCE.md for fixes")
sys.exit(1 if failed else 0)
