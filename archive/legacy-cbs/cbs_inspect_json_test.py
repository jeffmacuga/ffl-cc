import requests

url = "https://kjfha.football.cbssports.com/api/league/rosters?league_id=kjfha&version=3.0&response_format=json"

r = requests.get(url)

print("Status:", r.status_code)
print(r.text[:1000])