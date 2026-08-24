from bs4 import BeautifulSoup

with open(
    "cbs_source.html",
    "r",
    encoding="utf-8"
) as f:
    html = f.read()

soup = BeautifulSoup(html, "lxml")

tables = soup.find_all("table")

print(f"Found {len(tables)} tables")

for i, table in enumerate(tables):
    print(f"\nTABLE {i}")
    print(table.get_text(" ", strip=True)[:500])