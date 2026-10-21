import math
import sqlite3
import unicodedata

import pandas as pd

from optimizer import calculate_player_score
from services.database import DB_FILE


def _name_key(name):
    normalized = unicodedata.normalize("NFKD", str(name or "")).casefold()
    return "".join(character for character in normalized if character.isalnum())


def _number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _unique_player_lookup(records):
    lookup = {}
    ambiguous_names = set()
    for name, projection, average_points in records:
        key = _name_key(name)
        if not key or key in ambiguous_names:
            continue
        if key in lookup:
            del lookup[key]
            ambiguous_names.add(key)
            continue
        lookup[key] = {
            "projection": _number(projection),
            "average_points": _number(average_points),
        }
    return lookup


def build_espn_optimized_projection_lookup(league):
    records = (
        (
            player.name,
            (
                calculate_player_score(player)
                if any(
                    (_number(getattr(player, field, None)) or 0) > 0
                    for field in (
                        "projected_avg_points",
                        "projected_points",
                        "avg_points",
                    )
                )
                else None
            ),
            None,
        )
        for team in league.teams
        for player in team.roster
    )
    return _unique_player_lookup(records)


def build_cbs_projection_lookup(players):
    records = (
        (
            player.get("player_name"),
            player.get("projected_points"),
            None,
        )
        for player in players
    )
    return _unique_player_lookup(records)


def load_cbs_projection_lookup():
    with sqlite3.connect(DB_FILE) as connection:
        records = connection.execute(
            """
            SELECT player_name, projected_points, average_points
            FROM cbs_rosters
            """
        ).fetchall()
    return _unique_player_lookup(records)


def add_projection_columns(lineup_df, projection_lookups):
    if "Player" not in lineup_df:
        result = lineup_df.copy()
        for column in projection_lookups:
            result[column] = []
        result["Aggregate Projection"] = []
        return result

    projection_values = {column: [] for column in projection_lookups}
    aggregates = []
    for name in lineup_df["Player"]:
        key = _name_key(name)
        values = []
        for column, lookup in projection_lookups.items():
            projection = lookup.get(key, {}).get("projection")
            projection_values[column].append(projection)
            if projection is not None:
                values.append(projection)
        aggregates.append(sum(values) / len(values) if values else None)

    result = lineup_df.copy()
    for column, values in projection_values.items():
        result[column] = values
    result["Aggregate Projection"] = aggregates
    return result


def append_projection_totals(lineup_df, projection_columns):
    totals = {
        column: lineup_df[column].sum(min_count=1)
        for column in projection_columns
    }
    totals.update({
        column: ""
        for column in lineup_df.columns
        if column not in totals
    })
    totals["Player"] = "Total"
    return pd.concat(
        [lineup_df, pd.DataFrame([totals])],
        ignore_index=True,
    )
