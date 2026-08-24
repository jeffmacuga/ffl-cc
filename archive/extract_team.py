with open(
    "cbs_source.html",
    "r",
    encoding="utf-8"
) as f:
    html = f.read()

team = "Kalifornication"

idx = html.find(team)

print(f"Position: {idx}")

start = max(0, idx - 3000)
end = idx + 5000

print(html[start:end])