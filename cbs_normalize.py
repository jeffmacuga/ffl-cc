import json

def normalize_cbs_rosters(data):
    normalized_teams = []
    normalized_players = []

    teams = data["body"]["rosters"]["teams"]
    #teams = data["body"]["teams"]

    print("\n===== CBS NORMALIZATION =====")
    print(f"Teams returned by API: {len(teams)}")

    total_players = 0

    for team in teams:
        team_id = str(team["id"])

        roster_size = len(team.get("players", []))
        total_players += roster_size

        print(
            f"Team {team_id}: "
            f"{team.get('name')} "
            f"({roster_size} players)"
        )

        normalized_teams.append({
            "provider": "cbs",
            "provider_team_id": team_id,
            "team_name": team.get("name"),
            "abbreviation": team.get("abbr"),
            "division": team.get("division"),
            "logo_url": team.get("logo"),
        })

        for player in team.get("players", []):
            normalized_players.append({
                "provider": "cbs",
                "provider_team_id": team_id,
                "provider_player_id": str(player["id"]),
                "player_name": player.get("fullname"),
                "first_name": player.get("firstname"),
                "last_name": player.get("lastname"),
                "position": player.get("position"),
                "eligible_positions": to_json_text(
                    player.get("eligible_positions_display")
                ),
                "pro_team": player.get("pro_team"),
                "roster_position": player.get("roster_pos"),
                "roster_status": player.get("roster_status"),
                "bye_week": player.get("bye_week"),
                "keeper": bool(player.get("is_keeper")),
                "projected_points": to_float(
                    player.get("projected_points")
                ),
                "average_points": to_float(
                    player.get("avg_points")
                ),
                "ytd_points": to_float(
                    player.get("ytd_points")
                ),
            })

    print(f"Normalized teams: {len(normalized_teams)}")
    print(f"Normalized players: {len(normalized_players)}")
    print(f"Player total from API: {total_players}")

    return normalized_teams, normalized_players


def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def upsert_cbs_data(conn, teams, players):
    """Insert or update normalized CBS teams and roster players atomically."""
    team_sql = """
        INSERT INTO cbs_teams (
            provider_team_id,
            team_name,
            abbreviation,
            division,
            logo_url,
            updated_at
        ) VALUES (
            :provider_team_id,
            :team_name,
            :abbreviation,
            :division,
            :logo_url,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT(provider_team_id) DO UPDATE SET
            team_name = excluded.team_name,
            abbreviation = excluded.abbreviation,
            division = excluded.division,
            logo_url = excluded.logo_url,
            updated_at = CURRENT_TIMESTAMP
    """

    roster_sql = """
        INSERT INTO cbs_rosters (
            provider_team_id,
            provider_player_id,
            player_name,
            first_name,
            last_name,
            position,
            eligible_positions,
            pro_team,
            roster_position,
            roster_status,
            bye_week,
            keeper,
            projected_points,
            average_points,
            ytd_points,
            updated_at
        ) VALUES (
            :provider_team_id,
            :provider_player_id,
            :player_name,
            :first_name,
            :last_name,
            :position,
            :eligible_positions,
            :pro_team,
            :roster_position,
            :roster_status,
            :bye_week,
            :keeper,
            :projected_points,
            :average_points,
            :ytd_points,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT(provider_team_id, provider_player_id) DO UPDATE SET
            player_name = excluded.player_name,
            first_name = excluded.first_name,
            last_name = excluded.last_name,
            position = excluded.position,
            eligible_positions = excluded.eligible_positions,
            pro_team = excluded.pro_team,
            roster_position = excluded.roster_position,
            roster_status = excluded.roster_status,
            bye_week = excluded.bye_week,
            keeper = excluded.keeper,
            projected_points = excluded.projected_points,
            average_points = excluded.average_points,
            ytd_points = excluded.ytd_points,
            updated_at = CURRENT_TIMESTAMP
    """

    with conn:
        conn.executemany(team_sql, teams)
        conn.executemany(roster_sql, players)

def to_json_text(value):
    if value is None or isinstance(value, str):
        return value

    if isinstance(value, (list, tuple, dict)):
        return json.dumps(value, ensure_ascii=False)

    return str(value)