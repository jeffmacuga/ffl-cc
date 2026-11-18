from collections.abc import Mapping

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError


def get_cbs_team_mapping():
    try:
        access_config = st.secrets.get("access", {})
    except StreamlitSecretNotFoundError:
        access_config = {}

    if not isinstance(access_config, Mapping):
        raise ValueError("[access] must be a mapping.")

    configured_mapping = access_config.get("team_by_email", {})
    if not isinstance(configured_mapping, Mapping):
        raise ValueError("[access].team_by_email must be a mapping.")

    mapping = {}
    for email, team_id in configured_mapping.items():
        if not isinstance(email, str) or not email.strip():
            raise ValueError("CBS team mapping contains an invalid email.")
        team_id = str(team_id).strip()
        if not team_id.isdigit() or int(team_id) < 1:
            raise ValueError(
                f"CBS team ID for {email.strip()} must be a positive number."
            )
        mapping[email.strip().casefold()] = team_id
    return mapping


def get_authenticated_cbs_team_id():
    user = st.user
    if not user.is_logged_in or not getattr(user, "email_verified", False):
        return None

    email = str(getattr(user, "email", "") or "").strip().casefold()
    if not email:
        return None
    return get_cbs_team_mapping().get(email)


def _show_logout_button():
    st.sidebar.button("Sign out", on_click=st.logout)


def require_site_access():
    try:
        team_by_email = get_cbs_team_mapping()
    except ValueError as exc:
        st.error(f"Site access configuration is invalid: {exc}")
        return False

    if not team_by_email:
        st.error(
            "Site access is not configured. Map each member's Google email "
            "to their CBS team ID in `[access].team_by_email` in Streamlit "
            "secrets."
        )
        return False

    user = st.user
    if not user.is_logged_in:
        st.title("CBS League Sign In")
        st.write("Sign in with your Google account to access league data.")
        st.button("Continue with Google", on_click=st.login)
        return False

    email = str(getattr(user, "email", "") or "").strip().casefold()
    if not getattr(user, "email_verified", False):
        st.error("Google did not confirm a verified email address for this account.")
        _show_logout_button()
        return False

    if email not in team_by_email:
        st.error(
            "This Google account is not assigned to a CBS team. Contact the "
            "league administrator if you need access."
        )
        _show_logout_button()
        return False

    _show_logout_button()
    return True
