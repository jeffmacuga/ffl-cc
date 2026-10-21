import json
from pathlib import Path

data = json.loads(
    Path("discovery_output/rosters_test.json")
    .read_text(encoding="utf-8")
)

body = data.get("body", {})

print("Body keys:", list(body.keys()))

def describe(value, path="body", depth=0):
    if depth > 4:
        return

    if isinstance(value, dict):
        print(path, "DICT", list(value.keys()))
        for key, child in value.items():
            describe(child, f"{path}.{key}", depth + 1)

    elif isinstance(value, list):
        print(path, "LIST", len(value))
        if value:
            describe(value[0], f"{path}[0]", depth + 1)

    else:
        print(path, type(value).__name__)

describe(body)