"""The channel's series: "<NAME> – Words That Shape You" (NAME from the SERIES_CHARACTER
variable, default Kabir).

Every video takes one meaningful word (anger, discipline, trust...) and explains it through a
short stick-figure story about Kabir, a stickman boy with an orange scarf. The look is the
popular stickman-animation style (black lines on white, expressive body language, one accent
colour per feeling), made with NotebookLM's explainer video and a custom visual style.

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

NAME = os.getenv("SERIES_CHARACTER") or "Kabir"
SERIES = f"{NAME} – Words That Shape You"
CHARACTER = (
    f"{NAME}, a stick-figure boy: round head, simple dot eyes and expressive eyebrows, thin "
    f"black stick body, and a small orange scarf (his signature - always visible). {NAME}'s "
    "feelings show through big, clear body language and one accent colour: red scribbles and "
    "clenched fists for anger, a blue rain cloud for sadness, shaking knees for fear, a warm "
    "gold glow for calm, kindness, trust or discipline."
)
# NotebookLM explainer video, VideoStyle.CUSTOM (cinematic videos cannot take a style).
STYLE_PROMPT = (
    "Minimalist 2D stick-figure animation, like popular stickman life-lesson videos. Clean "
    "white background, bold black hand-drawn lines, stick figures with round heads and dot "
    "eyes, very expressive poses and movement. Props and places drawn as simple black line "
    "art. Only one accent colour per scene to show the feeling (red anger, blue sadness, "
    f"gold for good feelings). The main character {NAME} is a stick-figure boy with a small "
    "orange scarf and looks the same in every scene. No photos, no realistic images, no logos."
)
VISUAL_STYLE = (
    f"Tell the story visually with {NAME} as the main character in every scene: " + CHARACTER +
    " Show each story moment as a clear, simple scene. Use on-screen text only for the title "
    "and the word's meaning."
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


def write_script(word: str) -> dict:
    prompt = f"""Write the narration for one episode of the series "{SERIES}".
Today's word: {word.upper()}

The main character is {CHARACTER}

Structure (spoken narration only, 450-600 words):
1. Hook (1-2 sentences): a surprising question or truth about {word}.
2. The meaning: what "{word}" means, in one plain, dictionary-style sentence, then in
   simple everyday words.
3. {NAME}'s story (about 40% of the script): a short, original story where {NAME} meets
   {word} in daily life (school, work, friends, family, a market, a journey...). Show the
   feelings through {NAME}'s body language and actions (it will be drawn as a stickman
   animation, so describe clear, visual moments). A clear beginning, a turning point and an ending.
4. What {word} really does to us: to our mind, our body/energy and our relationships.
   General, widely accepted ideas only - no statistics, no studies, no medical claims.
5. Three short real-life moments where viewers meet {word} (relatable for India and the US).
6. How to handle it (if it is harmful) or how to build it (if it is good): 3 simple steps.
7. A short, memorable closing line that ties back to {NAME}'s story.

Rules: simple English, warm and wise tone, mature (for teens and adults, not a kids'
show), no scene directions, no [brackets], no emojis, no real people or brands.

Return JSON: {{"title": "<working title>", "script": "<the full narration>"}}"""
    result = llm.chat_json(prompt, SYSTEM, temperature=0.8, max_tokens=4000,
                           prefer=llm.WRITER_MODEL)
    words = len(result.get("script", "").split())
    for _ in range(2):
        if words >= 400:
            break
        log.info("Script only %d words, asking for a longer version", words)
        longer = llm.chat_json(f"""This narration is too short ({words} words). Rewrite it to
500-600 words with the same structure, story and tone. Expand the story and the real-life
moments.

{result.get("script", "")}

Return JSON: {{"title": "<working title>", "script": "<the full longer narration>"}}""",
                               SYSTEM, temperature=0.7, max_tokens=4000,
                               prefer=llm.WRITER_MODEL)
        if len(longer.get("script", "").split()) > words:
            result, words = longer, len(longer["script"].split())
    if words < 250:
        raise RuntimeError(f"Script too short ({words} words)")
    log.info("Script written for '%s' (%d words)", word, words)
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
