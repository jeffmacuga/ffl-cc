import requests

session = requests.Session()

session.cookies.set("cookie_name", "cookie_value")
session.cookies.set("another_cookie", "value")

r = session.get("https://kjfha.football.cbssports.com/")
print(r.status_code)

html = session.get(
    "https://kjfha.football.cbssports.com/"
).text

print(html[:2000])

r = session.get(
    "https://kjfha.football.cbssports.com/",
    allow_redirects=True
)

print(r.url)