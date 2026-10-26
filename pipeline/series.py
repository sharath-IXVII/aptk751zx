"""The channel's series: "<NAME> – Words That Shape You" (NAME from the SERIES_CHARACTER
variable, default Arjun).

Every video takes one meaningful word (anger, discipline, trust...) and explains it through a
short, meaningful animated story about Arjun, a stick-figure boy with an orange scarf
(stickman-animation look: black lines on white, expressive body language, one accent colour
per feeling). Made as a NotebookLM cinematic video (explainer + custom style as fallback).
The story comes first: it is planned, written and then reviewed by an editor pass so every
episode leaves the viewer with something that truly matters to them.

Format: the word and its plain meaning -> a short story -> what it does to us (mind, body,
relationships) -> 3 real-life moments -> how to handle or build it -> a closing line.

Words are never repeated (state/used_words.json is kept permanently).
"""

import datetime as dt
import json
import logging
import os
import random
from pathlib import Path

from pipeline import llm

log = logging.getLogger(__name__)

NAME = os.getenv("SERIES_CHARACTER") or "Arjun"
SERIES = f"{NAME} – Words That Shape You"
CHARACTER = (
    f"{NAME}, a stick-figure boy: round head, simple dot eyes and expressive eyebrows, thin "
    f"black stick body, and a small orange scarf (his signature - always visible). {NAME}'s "
    "feelings show through big, clear body language and one accent colour: red scribbles and "
    "clenched fists for anger, a blue rain cloud for sadness, shaking knees for fear, a warm "
    "gold glow for calm, kindness, trust or discipline."
)
# Explainer fallback: VideoStyle.CUSTOM. Cinematic videos get the same text in their instructions.
STYLE_PROMPT = (
    "Minimalist 2D stick-figure animation, like popular stickman life-lesson videos. Clean "
    "white background, bold black hand-drawn lines, stick figures with round heads and dot "
    "eyes, very expressive poses and movement. Props and places drawn as simple black line "
    "art. Only one accent colour per scene to show the feeling (red anger, blue sadness, "
    f"gold for good feelings). The main character {NAME} is a stick-figure boy with a small "
    "orange scarf and looks the same in every scene. No photos, no realistic images, no logos."
)
VISUAL_STYLE = (
    "Animate the whole video in this style: " + STYLE_PROMPT + f" Tell the story visually "
    f"with {NAME} as the main character in every scene: " + CHARACTER + " Show each story "
    "moment as a clear, moving animated scene. Use on-screen text only for the title and the "
    "word's meaning."
)
USED_FILE = Path("state/used_words.json")

# Grouped only for readability; one word per video, in a shuffled order.
WORDS = {
    "emotions": [
        "anger", "fear", "jealousy", "envy", "guilt", "shame", "regret", "loneliness",
        "anxiety", "stress", "sadness", "grief", "frustration", "boredom", "excitement",
        "joy", "contentment", "hope", "disappointment", "resentment", "insecurity", "pride",
        "ego", "nostalgia", "overthinking", "panic", "hate", "love", "attachment", "peace",
    ],
    "virtues": [
        "discipline", "trust", "patience", "honesty", "integrity", "respect", "gratitude",
        "kindness", "humility", "courage", "compassion", "empathy", "forgiveness", "loyalty",
        "responsibility", "generosity", "fairness", "self-control", "perseverance",
        "commitment", "accountability", "sincerity", "modesty", "tolerance", "dignity",
        "politeness", "reliability", "selflessness", "contentment", "wisdom",
    ],
    "mindset": [
        "consistency", "focus", "confidence", "self-doubt", "procrastination", "laziness",
        "motivation", "habit", "failure", "success", "ambition", "curiosity", "creativity",
        "comparison", "perfectionism", "resilience", "adaptability", "growth", "comfort zone",
        "excuses", "willpower", "determination", "positivity", "negativity", "silence",
        "solitude", "mindfulness", "acceptance", "letting go", "purpose",
    ],
    "life": [
        "time", "money", "saving", "greed", "debt", "simplicity", "minimalism", "health",
        "sleep", "rest", "balance", "priorities", "boundaries", "decision", "mistake",
        "change", "waiting", "luck", "opportunity", "risk", "sacrifice", "legacy", "habit loop",
        "delayed gratification", "first impressions", "reputation", "gossip", "lies",
        "promises", "advice",
    ],
    "relationships": [
        "friendship", "betrayal", "teamwork", "listening", "communication", "conflict",
        "apology", "saying no", "support", "care", "family", "loyalty", "jealousy in friendship",
        "criticism", "praise", "manners", "kind words", "harsh words", "misunderstanding",
        "giving", "sharing", "leadership", "followership", "influence", "peer pressure",
        "respecting elders", "helping others", "trust issues", "toxic people", "real friends",
    ],
}

SYSTEM = (
    "You are the head writer of a YouTube series that explains meaningful words through "
    "short, touching stories. Your scripts are warm, wise, simple and memorable, for teens "
    "and adults in India and the US."
)


def all_words() -> list[str]:
    seen, out = set(), []
    for group in WORDS.values():
        for w in group:
            if w not in seen:
                seen.add(w)
                out.append(w)
    return out


def used_words() -> list[str]:
    return json.loads(USED_FILE.read_text()) if USED_FILE.exists() else []


def mark_used(word: str) -> None:
    USED_FILE.parent.mkdir(parents=True, exist_ok=True)
    USED_FILE.write_text(json.dumps(used_words() + [word], indent=2, ensure_ascii=False))


def next_word() -> str:
    used = set(used_words())
    left = [w for w in all_words() if w not in used]
    if not left:  # every word done - start a second round
        log.info("All %d words used - starting again", len(all_words()))
        left = all_words()
    return random.choice(left)


def plan_story(word: str) -> dict:
    """Think of several stories first and keep the one that will mean the most to viewers."""
    return llm.chat_json(f"""Plan the story for an episode of "{SERIES}" about the word {word.upper()}.
The main character is {CHARACTER}

Think of 3 different original story ideas where {NAME} meets {word} in real life (home,
school, college, first job, friendship, family, money, a journey, a small town, a big city).
Then choose the ONE that is most meaningful: the one a viewer will recognise from their own
life, feel something about, and remember the next time {word} shows up for them.

A great story here has: a real, relatable situation; a moment of choice; a consequence the
viewer can feel (not preachy); a turning point where {NAME} understands something true about
{word}; and a quiet, hopeful ending. Visual moments that a stickman animation can show
clearly (actions, faces, gestures, places).

Return JSON: {{"ideas": ["<one line each>"], "chosen": <index>, "why": "<why it is the most
meaningful>", "outline": {{"setup": "...", "choice": "...", "consequence": "...",
"turning_point": "...", "ending": "...", "lesson": "<the one true sentence viewers should
remember>"}}}}""", SYSTEM, temperature=0.9, max_tokens=2500, prefer=llm.WRITER_MODEL)


def write_script(word: str) -> dict:
    plan = plan_story(word)
    outline = json.dumps(plan.get("outline", {}), ensure_ascii=False, indent=1)
    log.info("Story chosen: %s", plan.get("why", ""))
    prompt = f"""Write the narration for one episode of the series "{SERIES}".
Today's word: {word.upper()}

The main character is {CHARACTER}

STORY OUTLINE (use it - this is the heart of the episode):
{outline}

Structure (spoken narration only, 500-650 words):
1. Hook (1-2 sentences): a question or truth about {word} that makes the viewer stop.
2. {NAME}'s story (about 50% of the script): tell the outline as a gripping little story,
   in present tense, with small real details, one or two short lines of dialogue, and the
   feeling shown through what {NAME} does (it is animated, so describe visible moments).
3. The meaning: what "{word}" means, in one plain, dictionary-style sentence, then in simple
   everyday words - connected to what just happened in the story.
4. What {word} really does to us: our mind, our energy and our relationships. General, widely
   accepted ideas only - no statistics, no studies, no medical claims.
5. Three short real-life moments where viewers meet {word} (relatable in India and the US).
6. How to handle it (if harmful) or how to build it (if good): 3 simple, practical steps.
7. A closing line that returns to {NAME}'s story and leaves the viewer with the lesson:
   "{plan.get("outline", {}).get("lesson", "")}"

Rules: simple English, warm, honest and wise - never preachy; mature (teens and adults, not a
kids' show); no scene directions, no [brackets], no emojis, no real people or brands.

Return JSON: {{"title": "<working title>", "script": "<the full narration>"}}"""
    result = llm.chat_json(prompt, SYSTEM, temperature=0.8, max_tokens=4000,
                           prefer=llm.WRITER_MODEL)
    words = len(result.get("script", "").split())
    for _ in range(2):
        if words >= 450:
            break
        log.info("Script only %d words, asking for a longer version", words)
        longer = llm.chat_json(f"""This narration is too short ({words} words). Rewrite it to
550-650 words with the same structure, story and tone. Deepen the story and the real-life
moments.

{result.get("script", "")}

Return JSON: {{"title": "<working title>", "script": "<the full longer narration>"}}""",
                               SYSTEM, temperature=0.7, max_tokens=4000,
                               prefer=llm.WRITER_MODEL)
        if len(longer.get("script", "").split()) > words:
            result, words = longer, len(longer["script"].split())
    if words < 300:
        raise RuntimeError(f"Script too short ({words} words)")
    result = review_script(word, result)
    log.info("Script written for '%s' (%d words)", word, len(result["script"].split()))
    return result


def review_script(word: str, result: dict) -> dict:
    """Editor pass: score how meaningful the episode is and improve it if it is not great."""
    try:
        review = llm.chat_json(f"""You are a demanding story editor. Read this episode about
{word.upper()} and score it 1-10 on: (a) is the story emotionally real and relatable,
(b) does the viewer learn something true and useful about {word}, (c) is the ending
memorable, (d) is it free of clichés and preaching. If any score is below 8, rewrite the
script to fix it, keeping the structure, length (500-650 words), {NAME} and the spoken style.

SCRIPT:
{result["script"]}

Return JSON: {{"scores": {{"story": n, "lesson": n, "ending": n, "fresh": n}},
"rewritten": true/false, "script": "<the final script (unchanged if all scores >= 8)>"}}""",
                                SYSTEM, temperature=0.6, max_tokens=4000, prefer=llm.WRITER_MODEL)
    except Exception as exc:
        log.warning("Story review failed, keeping the script: %s", exc)
        return result
    log.info("Story review scores: %s (rewritten: %s)", review.get("scores"), review.get("rewritten"))
    new = review.get("script", "")
    if len(new.split()) >= 400:
        result["script"] = new
    return result


def create_script() -> dict:
    word = next_word()
    log.info("Today's word: %s", word)
    result = write_script(word)
    result.update({
        "topic": word,
        "series": SERIES,
        "word": word,
        "visual_style": VISUAL_STYLE,
        "style_prompt": STYLE_PROMPT,
        "sources": [],
        "research": {},
        "date": dt.date.today().isoformat(),
    })
    return result


def make_metadata(script: dict) -> dict:
    """Title, description, tags and title-screen text for a series episode."""
    word = script["word"]
    return llm.chat_json(f"""You are a YouTube SEO expert for the series "{SERIES}": each
episode explains one meaningful word through a short stick-figure story about {NAME}, a
stickman boy with an orange scarf. Audience: teens and adults in India and the US.

Episode word: {word}
Script:
{script["script"]}

Write:
- title: 45-65 characters, the word in CAPITALS near the start, the way people search,
  curiosity-driven and honest. Examples: "What ANGER Really Does To You", "DISCIPLINE: The
  Quiet Power Most People Ignore", "Why TRUST Breaks So Easily". No emojis.
- cover_text: 1-3 words for the opening title screen and thumbnail, usually just the word,
  e.g. "ANGER" or "WHAT IS TRUST?"
- description: 3 parts separated by blank lines: 1) two hook sentences with the main
  keywords ("what is {word}", "meaning of {word}"), 2) a 3-4 sentence summary of the story
  and the lesson, 3) "In this video:" followed by 4 short lines starting with "- ".
  Mention the series name once. No links, no hashtags.
- hashtags: 3, e.g. "#LifeLessons"
- tags: 15 search tags, e.g. "what is {word}", "meaning of {word}", "{word} explained",
  "life lessons", "motivation", most important first.

Return JSON: {{"title": "...", "cover_text": "...", "description": "...",
"hashtags": ["#..."], "tags": ["..."]}}""", temperature=0.6, max_tokens=2000,
                          prefer=llm.WRITER_MODEL)
