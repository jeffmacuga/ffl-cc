import browser_cookie3
import requests

url = "https://kjfha.football.cbssports.com/standings/overall"

cookies = {
   "auth_session": "eyJhbGciOiJkaXIiLCJlbmMiOiJBMjU2R0NNIn0..RVi__LoXA_INwRw8.yKzM91pCq9Yb3amZqS_yauHm2LiXRn_aDBJHnXUl4noZTXiavrO8qdEUyDY8mXd-CmBkSD3gc2JzE6REpLB7Ng8lhJwUptaQUds9WyvKgPzM9OeAle4gQ52ZaUUPF4SEyNbLstn71lIhv1kEKvUNk8enzgO2V0Nyk8mrLOmg8i5qNmzQYfsIZFjwFvm9Pkph-WW8BPCQMpzTt17ail2tGmQLeJm7t2YZucGnmmMjZqh1Sq3mncr49WKam9sfGEzuWexgZTJKxFzPvtbSVIV0rEbK6TWl_WwT2d8fbhMvqC3FBKkTN9bLhS_PKFJz0kzmtuppgM6g2VSzg2sX_5ikKF4OnWeIryLpdPVBCc0sW3Pny8llQn1I1eAdF28VmgaBaKrCya_ZR7KHH0v-vuZIZ6mqR0pHSW0kQku5eLii5d7XEtlLtpzvEg8AJr8tp9N3AQrfMKRDLBVtimOLY3L6wR_dJSuGcUIQBvq4-tihEBJ2nWnKPZ2tn7Dc4pT8qrrwXoG0mOu3V2GrnGqMt0LvzCsRfj047cut9Q4.q5jQhEaUwVG7FZ3-lIaOrg"
}
response = requests.get(
    url,
    cookies=cookies
)

print(response.status_code)

with open(
    "cbs_standings.html",
    "w",
    encoding="utf-8"
) as f:
    f.write(response.text)


print("Saved page")