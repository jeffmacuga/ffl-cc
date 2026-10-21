import json
from types import SimpleNamespace

from discover_cbs_api import (
    LEAGUE_HOST,
    _is_candidate,
    sanitize_post_data,
    sanitize_url,
)


def make_request(method, url):
    return SimpleNamespace(method=method, url=url)


def test_sanitize_url_redacts_credentials_but_keeps_team_ids():
    url = (
        "https://kjfha.football.cbssports.com/api/league/lineup"
        "?team_id=15&access_token=private&week=7"
    )

    result = sanitize_url(url)

    assert "team_id=15" in result
    assert "week=7" in result
    assert "access_token=%5BREDACTED%5D" in result
    assert "private" not in result


def test_sanitize_post_data_redacts_nested_secrets():
    body = json.dumps({
        "team_id": "15",
        "lineup": [{"player_id": "123", "slot": "FLEX"}],
        "csrf_token": "private",
        "userid": "member-id",
    })

    result = sanitize_post_data(body, "application/json")

    assert result["team_id"] == "15"
    assert result["lineup"] == [{"player_id": "123", "slot": "FLEX"}]
    assert result["csrf_token"] == "[REDACTED]"
    assert result["userid"] == "[REDACTED]"


def test_sanitize_form_data_redacts_credentials():
    result = sanitize_post_data(
        "team_id=15&player_id=123&session_token=private&id=member-id",
        "application/x-www-form-urlencoded",
    )

    assert result == {
        "team_id": "15",
        "player_id": "123",
        "session_token": "[REDACTED]",
        "id": "[REDACTED]",
    }


def test_detects_cbs_set_lineup_action_outside_api_path():
    request = make_request(
        "GET",
        f"https://{LEAGUE_HOST}/teams/roster-report/8/7/?action=set-lineup",
    )

    assert _is_candidate(request)


def test_detects_write_request_to_roster_path():
    request = make_request(
        "POST",
        f"https://{LEAGUE_HOST}/teams/8/roster",
    )

    assert _is_candidate(request)


def test_detects_write_request_to_unexpected_drop_path():
    request = make_request(
        "POST",
        f"https://{LEAGUE_HOST}/players/transactions/submit",
    )

    assert _is_candidate(request)


def test_ignores_write_request_on_unrelated_cbs_subdomain():
    request = make_request(
        "POST",
        "https://api.cbssports.com/football/lineup",
    )

    assert not _is_candidate(request)


def test_detects_get_transaction_action():
    request = make_request(
        "GET",
        f"https://{LEAGUE_HOST}/players?action=drop&player_id=123",
    )

    assert _is_candidate(request)


def test_ignores_roster_trends_widget_get():
    request = make_request(
        "GET",
        f"https://{LEAGUE_HOST}/component/homepage/roster-trends/added",
    )

    assert not _is_candidate(request)


def test_ignores_unrelated_and_external_requests():
    unrelated = make_request(
        "GET",
        f"https://{LEAGUE_HOST}/account/profile",
    )
    external = make_request(
        "POST",
        "https://example.com/api/lineup",
    )
    unrelated_get = make_request(
        "GET",
        f"https://{LEAGUE_HOST}/players/playerpage/123",
    )

    assert not _is_candidate(unrelated)
    assert not _is_candidate(external)
    assert not _is_candidate(unrelated_get)
