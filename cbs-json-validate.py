import json
from pathlib import Path

path = Path("discovery_output/sample_01633291f43c.json")
data = json.loads(path.read_text(encoding="utf-8"))

print("Top-level type:", type(data).__name__)

if isinstance(data, dict):
    print("Top-level keys:", list(data.keys()))

    for key, value in data.items():
        if isinstance(value, list):
            print(f"{key}: list containing {len(value)} items")
        elif isinstance(value, dict):
            print(f"{key}: dict keys={list(value.keys())[:20]}")
        else:
            print(f"{key}: {type(value).__name__}")