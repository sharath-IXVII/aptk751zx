"""Viewer comments check (daily): read new comments on the channel, find the ones that point out
a mistake or something missing, and save each as a lesson in state/viewer_feedback.json.
The script writer and the fact-checker read these lessons, so the same mistake is not repeated.
Also prints a short report of all new comments. Nothing is posted or deleted."""
import datetime as dt
import json
import logging
import re
import sys
from pathlib import Path

sys.path.insert(0, ".")
logging.basicConfig(level=logging.INFO, format="%(message)s")
from pipeline.youtube_upload import _client

FEEDBACK = Path("state/viewer_feedback.json")
SEEN = Path("state/comments_seen.json")
HINTS = re.compile(r"\b(wrong|incorrect|mistake|error|not correct|isn'?t correct|false|misleading|"
                   r"reverse[d]?|backwards|opposite|polarity|missing|didn'?t show|no steps|"
                   r"not working|doesn'?t work|fake|clickbait|where (is|are) the|you forgot|actually)\b", re.I)


def load(p: Path, default):
    return json.loads(p.read_text()) if p.exists() else default


def fetch(yt, days: int = 14) -> list[dict]:
    ch = yt.channels().list(part="id", mine=True).execute()["items"][0]["id"]
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    out, tok = [], None
    for _ in range(5):
        r = yt.commentThreads().list(part="snippet", allThreadsRelatedToChannelId=ch, maxResults=100,
                                     order="time", textFormat="plainText", pageToken=tok).execute()
        for t in r.get("items", []):
            c = t["snippet"]["topLevelComment"]["snippet"]
            when = dt.datetime.fromisoformat(c["publishedAt"].replace("Z", "+00:00"))
            if when < since:
                return out
            out.append({"id": t["id"], "video_id": t["snippet"].get("videoId", ""),
                        "author": c.get("authorDisplayName", ""), "text": c["textDisplay"][:1000],
                        "date": c["publishedAt"][:10], "likes": c.get("likeCount", 0)})
        tok = r.get("nextPageToken")
        if not tok:
            break
    return out


def titles(yt, ids: list[str]) -> dict:
    out = {}
    for i in range(0, len(ids), 50):
        for v in yt.videos().list(part="snippet", id=",".join(ids[i:i + 50])).execute().get("items", []):
            out[v["id"]] = v["snippet"]["title"]
    return out


def classify(comments: list[dict]) -> list[dict]:
    """Ask the AI which comments report a real mistake; fall back to keywords if it fails."""
    if not comments:
        return []
    try:
        from pipeline import llm
        listing = "\n".join(f'{i}. [video: {c["title"][:80]}] {c["text"][:400]}' for i, c in enumerate(comments))
        r = llm.chat_json(f"""These are new YouTube comments on an educational channel. Find ONLY the
comments that point out a mistake, an inaccuracy, a wrong diagram/connection, or that the video
did not deliver what its title promised (e.g. missing steps). Ignore praise, questions, spam.

{listing}

For each one, write a short, general lesson the script writer must follow from now on (e.g.
"Draw electrolytic capacitors with + to the higher voltage; state polarity in the script").

Return JSON: {{"issues": [{{"n": <comment number>, "problem": "<what was wrong>",
"lesson": "<rule to follow in every future video>"}}]}}""", temperature=0.1, max_tokens=3000)
        out = []
        for it in r.get("issues", []):
            n = int(it.get("n", -1))
            if 0 <= n < len(comments):
                out.append({**comments[n], "problem": it.get("problem", ""), "lesson": it.get("lesson", "")})
        return out
    except Exception as exc:
        print("AI check failed, using keywords:", str(exc)[:200])
        return [{**c, "problem": c["text"][:200], "lesson": f'Viewer reported: "{c["text"][:200]}"'}
                for c in comments if HINTS.search(c["text"])]


def main():
    yt = _client()
    seen = set(load(SEEN, []))
    new = [c for c in fetch(yt) if c["id"] not in seen]
    t = titles(yt, sorted({c["video_id"] for c in new if c["video_id"]}))
    for c in new:
        c["title"] = t.get(c["video_id"], "(channel)")
    issues = classify(new)
    feedback = load(FEEDBACK, [])
    feedback += [{k: i[k] for k in ("date", "video_id", "title", "text", "problem", "lesson")} for i in issues]
    FEEDBACK.parent.mkdir(parents=True, exist_ok=True)
    FEEDBACK.write_text(json.dumps(feedback[-300:], indent=1, ensure_ascii=False))
    SEEN.write_text(json.dumps((sorted(seen | {c["id"] for c in new}))[-5000:]))

    print(f"\n========== VIEWER COMMENTS: {len(new)} new ==========")
    for c in new:
        print(f'- [{c["date"]}] {c["title"][:60]}: {c["text"][:200]}')
    print(f"\n========== MISTAKES REPORTED: {len(issues)} ==========")
    for i in issues:
        print(f'! {i["title"][:70]} (https://youtu.be/{i["video_id"]})\n'
              f'    viewer: {i["text"][:250]}\n    lesson saved: {i["lesson"]}')
    if not issues:
        print("None - no viewer reported a mistake.")


if __name__ == "__main__":
    main()
