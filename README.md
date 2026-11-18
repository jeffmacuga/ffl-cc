# Fantasy Command Center

## CBS member access

The app uses one individual access code per CBS team. Members enter their code
on the sign-in screen; the app associates that code with the configured team
and limits roster and lineup pages to that team. Shared standings and matchup
summaries remain visible to all signed-in members.

Generate a different high-entropy code for each member. For example, run this
command once per member:

```bash
python -c "import secrets; print(secrets.token_urlsafe(24))"
```

In the Streamlit Cloud app settings under **Secrets**, add the generated codes
and matching CBS team IDs:

```toml
[access]
team_access_codes = [
  { code = "PASTE_MEMBER_1_CODE_HERE", team_id = "1", leagues = ["CBS"] },
  { code = "PASTE_MEMBER_2_CODE_HERE", team_id = "2", leagues = ["CBS", "Kick-Butt Football"] },
]
```

The `leagues` list controls which league options appear in the sidebar. Omit it
to retain the existing behavior for a member that should see every configured
league. When only one league is allowed, the league selector is hidden and that
league is selected automatically.

Use the numeric CBS team IDs from the `cbs_teams` data. Keep these codes in
Streamlit secrets, never in the repository. Send each member only their own
code using a private channel. To revoke access, remove that code from secrets;
existing sessions using it are denied on their next app run. Generate a new
code if a member's code is lost or exposed.

Google OAuth `[auth]` settings are no longer required for this app. The code
gate is inside the app; Streamlit Community Cloud may separately require the
app owner to share the app with users or make it public so they can reach the
sign-in screen.

The CBS Trade Analyzer is unavailable because it requires access to both
teams' rosters.

## Lineup explanations

The CBS and ESPN lineup previews include concise, rule-based explanations of
the optimizer's choices and available projection totals. These explanations
are generated locally from app data and do not require an AI API key or send
roster data to an external AI provider. Projections are estimates, and users
should review missing or zero values and late injury/news changes.

## Automatic CBS data refresh

The `CBS data refresh` GitHub Actions workflow imports CBS teams, rosters, and
standings daily at 11:17 UTC and can also be started manually from the Actions
tab. It uses the `CBS_STORAGE_STATE` repository Actions secret, the same saved
CBS browser login state used by the lineup workflow, and commits an updated
`fantasy.db` when the import completes. If Streamlit Community Cloud is
connected to this repository and branch, that commit triggers a redeploy with
the refreshed data.
