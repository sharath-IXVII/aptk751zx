"""Measure search demand for some phrases (median views of the top 10 YouTube results)."""
import logging, sys
logging.basicConfig(level=logging.INFO)
sys.path.insert(0, ".")
from pipeline.searchtopics import search_demand
import os
k = os.getenv("YOUTUBE_API_KEY") or ""
print("YOUTUBE_API_KEY set:", bool(k), "length", len(k))
for q in sys.argv[1:]:
    print(f"{search_demand(q) or 0:>12,}  {q}")
