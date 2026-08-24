from espn_api.football import League
import pandas as pd
import sqlite3

# ==========================================
# ESPN CONFIG
# ==========================================

LEAGUE_ID = 465649962
YEAR = 2026

ESPN_S2 = "AEAtk3BaOcADlcYivYJmH7p2BvHMp4vpKCmVn%2B6aucUeZN3pYFIeecyM%2Fst66dXM0tvd9%2FMudnDZva8KkNLrB57N1sMa0MaVtOybvbSe8OdIf3SWLuB9Hzk5UQI7LeHOUVj2lQVEwSa6Q%2F85csfri%2FlU8RIc5gTNfkkrZzLbI2L8owzcUKxYwxPSuHI%2FKlBwx9ji%2BXJahc3FfVKI0UCZ2jNmKjJc37FzQ7z1qqxL5RQrwFHHks4gS1qrrrpvKwOZGDBNNPCR9Q3lzdV7lI4uQkTfmo%2Bw7%2FaoyQ74%2FPxj%2FmHtl2V6PZ1%2FsltH6TcZ65k7SS%2FuKk1nQsW0vislxG61jELHQ%2FbcAAYwxMGWVz35AOvRe0hYAXGz8Ie707pcgXCic1M%3D"
SWID = "{E8418BEB-2939-480F-818B-EB2939E80F06}"

# -----------------------------------
# CONNECT
# -----------------------------------

league = League(
    league_id=LEAGUE_ID,
    year=YEAR,
    espn_s2=ESPN_S2,
    swid=SWID
)

# -----------------------------------
# GET PLAYERS
# -----------------------------------

players = league.free_agents(size=2000)

print(f"Found {len(players)} players")

# -----------------------------------
# BUILD DATAFRAME
# -----------------------------------

rows = []

for p in players:

    if p.position not in ["QB", "RB", "WR", "TE"]:
        continue

    rows.append({
        "player_name": p.name,
        "position": p.position,
        "ranking": p.posRank,
        "adp": p.percent_owned,
        "projected_points": p.projected_total_points,
        "tier": None
    })

df = pd.DataFrame(rows)

# -----------------------------------
# CREATE OVERALL RANKING
# -----------------------------------

df = df.sort_values(
    "projected_points",
    ascending=False
)

df.reset_index(drop=True, inplace=True)

df["ranking"] = df.index + 1

# -----------------------------------
# TIERS
# -----------------------------------

def get_tier(rank):

    if rank <= 12:
        return 1
    elif rank <= 36:
        return 2
    elif rank <= 72:
        return 3
    elif rank <= 120:
        return 4
    else:
        return 5

df["tier"] = df["ranking"].apply(get_tier)

# -----------------------------------
# SAVE TO SQLITE
# -----------------------------------

conn = sqlite3.connect("C:\\Users\\User\\source\\ffl-mgr\\fantasy.db")

df.to_sql(
    "player_rankings",
    conn,
    if_exists="replace",
    index=False
)

conn.close()

print(f"✅ Imported {len(df)} players")
print(df.head(20))