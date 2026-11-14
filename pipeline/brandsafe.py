"""Remove other creators' / brands' channel names from our titles, descriptions and tags.
Search trends often contain them (e.g. "network theory neso academy"); using them in our metadata
looks misleading to viewers and to YouTube."""

import re

BRANDS = [
    "Neso Academy", "Neso", "Gate Smashers", "Unacademy", "Physics Wallah", "PhysicsWallah", "PW Skills",
    "Byju's", "Byjus", "BYJU'S", "Khan Academy", "NPTEL", "Apna College", "CodeWithHarry", "Code With Harry",
    "Telusko", "freeCodeCamp", "Simplilearn", "Edureka", "Great Learning", "Jenny's Lectures", "Abdul Bari",
    "Kunal Kushwaha", "Striver", "takeUforward", "Love Babbar", "NetworkChuck", "David Bombal", "John Hammond",
    "The Cyber Mentor", "Tech With Tim", "Programming with Mosh", "ElectroBOOM", "GreatScott", "Ali Abdaal",
    "Veritasium", "Kurzgesagt", "Vsauce", "Mark Rober", "Magic School Bus", "Engineering Mindset",
    "All About Electronics", "Ekeeda", "Gradeup", "Made Easy", "ACE Academy", "Testbook", "Vedantu",
    "Intellipaat", "Coursera", "Udemy", "Neural Nine", "Fireship", "Computerphile", "3Blue1Brown",
]
_RX = re.compile(r"(?i)(?<![\w])(" + "|".join(re.escape(b) for b in sorted(BRANDS, key=len, reverse=True)) + r")(?![\w])")


def clean(text: str) -> str:
    if not text:
        return text
    out = _RX.sub("", text)
    out = re.sub(r"\s+([:,.!?])", r"\1", out)              # space before punctuation
    out = re.sub(r"\|\s*\|", "|", out)
    out = re.sub(r"([:|-])\s*([:|-])", r"\1", out)         # doubled separators
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"(?m)^\s*[:|,-]\s*", "", out)            # leading separator
    out = re.sub(r"\s*[:|,-]\s*$", "", out.strip())        # trailing separator
    out = re.sub(r"\b(The|A|An)\s*:", ":", out).strip()
    return out.strip()


def clean_meta(meta: dict) -> dict:
    m = dict(meta)
    m["title"] = clean(m.get("title", "")) or m.get("title", "")
    m["description"] = "\n".join(clean(l) if _RX.search(l) else l for l in m.get("description", "").split("\n"))
    m["tags"] = [t for t in (clean(t) for t in m.get("tags", [])) if t]
    return m


if __name__ == "__main__":
    for t in ["Network Theory Neso Academy: Thevenin's Theorem Simplify Any Circuit",
              "How Computers Work: The Magic School Bus Guide to Binary & Circuits",
              "Python Tutorial | CodeWithHarry style | Learn Fast"]:
        print(t, "->", clean(t))
