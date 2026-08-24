import json
from pathlib import Path

path = Path("discovery_output/sample_01633291f43c.json")
data = json.loads(path.read_text(encoding="utf-8"))

feed = data["body"]["feed"]

print("Feed type:", type(feed).__name__)

if isinstance(feed, dict):
    print("Feed keys:", list(feed.keys()))

    for key, value in feed.items():
        if isinstance(value, list):
            print(f"{key}: list with {len(value)} items")
            if value:
                print("First item keys:", list(value[0].keys()))
        elif isinstance(value, dict):
            print(f"{key}: dict keys={list(value.keys())[:20]}")
        else:
            print(f"{key}: {type(value).__name__}")