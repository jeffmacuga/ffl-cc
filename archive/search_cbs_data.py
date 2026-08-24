# search_cbs_data.py

with open(
    "cbs_source.html",
    "r",
    encoding="utf-8"
) as f:
    html = f.read()

terms = [
    "3MTA3",
    "Kalifornication",
    "Real Huffy",
    '"wins"',
    '"losses"',
    '"points"',
    '"standings"',
    '"teams"',
    '"owners"',
]

for term in terms:
    pos = html.find(term)
    print(term, pos)