"""News mode test (nothing is published): headlines -> AI picks a story -> research."""
import logging, sys
sys.path.insert(0, ".")
logging.basicConfig(level=logging.INFO, format="%(message)s")
from pipeline import news
h = news.headlines(); print(len(h), "headlines"); print("\n".join(h[:15]))
s = news.pick_story([]); print("PICKED:", s)
facts, items = news.gather(s["query"]); print(len(items), "news items,", len(facts), "chars of facts"); print(facts[:1500])
