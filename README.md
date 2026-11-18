# Fantasy Command Center

## Site access

The app requires an approved Google account before it loads league data. Set up
a Google OAuth client and configure the redirect URL as your app URL followed
by `/oauth2callback` in Google Cloud. Then configure Streamlit secrets in the
deployment settings or in `.streamlit/secrets.toml` for local development:

```toml
[auth]
redirect_uri = "http://localhost:8501/oauth2callback"
cookie_secret = "replace-with-a-long-random-secret"
client_id = "your-google-oauth-client-id"
client_secret = "your-google-oauth-client-secret"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"

[access.team_by_email]
"member1@example.com" = "CBS_TEAM_ID_1"
"member2@example.com" = "CBS_TEAM_ID_2"
```

Set `redirect_uri` to the public app URL plus `/oauth2callback` in production.
Use a unique, strong value for `cookie_secret`, and add the same redirect URL
to the Google OAuth client's authorized redirect URIs.

Never commit OAuth secrets. If the team mapping is missing or invalid, the app
fails closed and displays a setup message. Find each CBS team ID in the
`cbs_teams` table or the CBS team data, then map each member's verified Google
email to that numeric ID. Members can see shared CBS standings and matchups,
but roster pages and lineup previews are limited to their assigned team. The
CBS trade analyzer is unavailable because it requires access to both teams'
rosters.
