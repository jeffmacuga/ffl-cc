with open(
    "cbs_source.html",
    "r",
    encoding="utf-8"
) as f:
    html = f.read()

idx = html.find("3MTA3")

print(html[idx-3000:idx+3000])