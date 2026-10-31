"""The channel's content: original animated stories with a twist (an entertainment channel).

Each episode is a new, original 5-6 minute story - mystery, emotional, suspense, drama, funny,
inspiring... - told in the same stick-figure animation style (pipeline/series.py). Structure:
a cold-open hook (the most dramatic moment first) -> the story -> the twist -> a one-line
ending that makes people comment. Genres rotate; story ideas are never repeated
(state/used_stories.json is kept permanently).
"""

import datetime as dt
import json
import logging
from pathlib import Path

from pipeline import llm
from pipeline.series import MOTION, STYLE_PROMPT

log = logging.getLogger(__name__)

SERIES = "Stories With a Twist"
USED_FILE = Path("state/used_stories.json")

GENRES = {
    "mystery": "a puzzling situation, clues the viewer can follow, a reveal that changes everything",
    "emotional": "a moving story about family, friendship or sacrifice, with a heart-touching twist",
    "suspense": "tension that builds scene by scene (no gore, no graphic violence), a shocking turn",
    "drama": "relationships, secrets and choices, ending with a reveal that flips who was right",
    "funny": "a comedy of errors or misunderstanding with a clever, laugh-out-loud payoff",
    "inspiring": "an underdog story with an unexpected turn that proves someone wrong",
    "karma": "someone gets exactly what they gave - a satisfying justice twist",
    "family secret": "a hidden truth in a family that comes out at the perfect moment",
    "clever plan": "a smart character outwits someone with a plan the viewer only sees at the end",
    "spooky": "an eerie, family-safe mystery that seems supernatural but has a surprising explanation",
}

SYSTEM = (
    "You are the head writer of a hit animated storytelling channel for teens and adults in "
    "India and the US. You write original, gripping short stories with unforgettable twists, "
    "told as spoken narration."
)

CAST = (
    "Choose the characters that fit the story - any ages and jobs - with simple names that feel "
    "natural in India or the US. Everyone is a stick figure: round head, dot eyes and expressive "
    "eyebrows, thin black stick body; give each person one small detail so they are easy to tell "
    "apart (a scarf, glasses, a cap, a school bag, a walking stick, a hair bun)."
)
VISUAL_STYLE = (
    "Animate the whole video in this style: " + STYLE_PROMPT + " Characters: " + CAST +
    " Show every story moment as a clear, moving animated scene, with suspenseful pacing "
    "and a dramatic reveal at the twist. Use on-screen text only for the title. " + MOTION
)


def used() -> list[dict]:
    return json.loads(USED_FILE.read_text()) if USED_FILE.exists() else []


def mark_used(title: str, premise: str, genre: str) -> None:
    USED_FILE.parent.mkdir(parents=True, exist_ok=True)
    entries = used() + [{"title": title, "premise": premise, "genre": genre,
                         "date": dt.date.today().isoformat()}]
    USED_FILE.write_text(json.dumps(entries, indent=1, ensure_ascii=False))


def next_genre() -> str:
    """Rotate genres: the one used least (and least recently) goes next."""
    history = [u.get("genre") for u in used()]
    counts = {g: history.count(g) for g in GENRES}
    last_seen = {g: (max(i for i, h in enumerate(history) if h == g) if g in history else -1)
                 for g in GENRES}
    return min(GENRES, key=lambda g: (counts[g], last_seen[g]))


def plan_story(genre: str) -> dict:
    past = [u["premise"] for u in used()[-150:]]
    return llm.chat_json(f"""Create the idea for a new animated short story.
Genre: {genre} - {GENRES[genre]}

Think of 4 completely original story ideas (not famous stories, films or urban legends;
no real people or brands). Then choose the ONE with the strongest hook and the most
surprising, satisfying twist - one that makes viewers say "I did NOT see that coming" and
want to tell someone. The twist must be fair: clues are there if you look back.

Do NOT reuse or closely resemble these earlier stories:
{json.dumps(past, ensure_ascii=False)}

Keep it suitable for teens and adults: no gore, no sexual content, no hate, no self-harm.

Return JSON: {{"ideas": ["<one line each>"], "chosen": <index>,
"premise": "<one sentence summary of the chosen story>",
"outline": {{"characters": "<names, ages, one look detail each>", "cold_open": "<the most
dramatic moment, shown first>", "setup": "...", "rising_tension": "...", "twist": "...",
"ending": "<final image and a one-line question to the viewer>"}}}}""",
                         SYSTEM, temperature=1.0, max_tokens=2500, prefer=llm.WRITER_MODEL)


def write_script(genre: str) -> dict:
    plan = plan_story(genre)
    outline = json.dumps(plan.get("outline", {}), ensure_ascii=False, indent=1)
    log.info("Story (%s): %s", genre, plan.get("premise", ""))
    prompt = f"""Write the spoken narration for this animated short story ({genre}).

STORY OUTLINE:
{outline}

Rules:
- 650-800 words, spoken narration only (no scene directions, no [brackets], no emojis).
- Start with the COLD OPEN: the first 2-3 sentences drop the viewer straight into the most
  dramatic moment so they cannot stop watching. Then go back ("Three days earlier...").
- Vivid, visual, present-tense storytelling with short punchy sentences, a few lines of
  dialogue, and clear actions that can be animated (running, hiding, opening, turning).
- Build tension; hide fair clues; deliver the twist late, in a short, powerful moment.
- End with one memorable closing line and a short question to the viewer
  (e.g. "What would you have done?").
- Simple English for India and the US, suitable for teens and adults, no real people or brands.

Return JSON: {{"title": "<working title>", "script": "<the full narration>"}}"""
    result = llm.chat_json(prompt, SYSTEM, temperature=0.9, max_tokens=4500,
                           prefer=llm.WRITER_MODEL)
    words = len(result.get("script", "").split())
    if words < 450:
        longer = llm.chat_json(f"""This narration is too short ({words} words). Rewrite it to
650-800 words, same story, twist and style; build more tension before the twist.

{result.get("script", "")}

Return JSON: {{"title": "<working title>", "script": "<the full narration>"}}""",
                               SYSTEM, temperature=0.8, max_tokens=4500,
                               prefer=llm.WRITER_MODEL)
        if len(longer.get("script", "").split()) > words:
            result, words = longer, len(longer["script"].split())
    if words < 350:
        raise RuntimeError(f"Story too short ({words} words)")
    result = review(result)
    result["premise"] = plan.get("premise", "")
    log.info("Story written (%d words)", len(result["script"].split()))
    return result


def review(result: dict) -> dict:
    """Editor pass: is the hook gripping, the twist surprising and fair, the ending strong?"""
    try:
        r = llm.chat_json(f"""You are a demanding story editor for a viral storytelling channel.
Score this story 1-10 on: hook (first 3 sentences grab you), tension, twist (surprising AND
fair), ending (memorable). If any score is below 8, rewrite it to fix that, keeping the
story, length (650-800 words) and spoken style.

STORY:
{result["script"]}

Return JSON: {{"scores": {{"hook": n, "tension": n, "twist": n, "ending": n}},
"rewritten": true/false, "script": "<the final story>"}}""", SYSTEM, temperature=0.6,
                          max_tokens=4500, prefer=llm.WRITER_MODEL)
    except Exception as exc:
        log.warning("Story review failed, keeping the story: %s", exc)
        return result
    log.info("Story review scores: %s (rewritten: %s)", r.get("scores"), r.get("rewritten"))
    if len(r.get("script", "").split()) >= 450:
        result["script"] = r["script"]
    return result


def create_script() -> dict:
    genre = next_genre()
    result = write_script(genre)
    result.update({"topic": result.get("premise") or result["title"], "series": SERIES,
                   "genre": genre, "visual_style": VISUAL_STYLE, "style_prompt": STYLE_PROMPT,
                   "sources": [], "research": {}, "date": dt.date.today().isoformat()})
    return result


def make_metadata(script: dict) -> dict:
    return llm.chat_json(f"""You are a YouTube packaging expert for a viral animated
storytelling channel (teens and adults, India and the US). Package this {script["genre"]} story.

STORY:
{script["script"]}

Write:
- title: 40-65 characters, a curiosity-gap story title that makes people NEED to know what
  happens, without giving away the twist. Honest to the story. Examples: "He Found His Own
  Missing Poster...", "The Delivery Boy Who Saved a Billionaire", "Nobody Believed The
  Old Watchman Until...". No emojis, no all-caps sentences.
- cover_text: 2-4 punchy words for the opening title screen and thumbnail (e.g. "HIS OWN POSTER?").
- short_hook: one gripping sentence (max 12 words) for the vertical Short, e.g.
  "He found a missing poster... with HIS face on it."
- description: 2 short paragraphs: a hook that teases the story (no spoilers), then
  "Watch till the end - you won't see the twist coming." and a question for the comments.
  No links, no hashtags.
- hashtags: 3, e.g. "#story", "#animation", "#plottwist"
- tags: 15 search tags (e.g. "animated story", "story with twist", "{script["genre"]} story",
  "moral story", "plot twist"), most important first.

Return JSON: {{"title": "...", "cover_text": "...", "short_hook": "...", "description": "...",
"hashtags": ["#..."], "tags": ["..."]}}""", temperature=0.7, max_tokens=2000,
                          prefer=llm.WRITER_MODEL)
