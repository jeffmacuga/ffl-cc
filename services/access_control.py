import hashlib
import hmac
from collections.abc import Mapping

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

SESSION_CODE_HASH_KEY = "cbs_access_code_hash"


def _get_access_config():
    try:
        access_config = st.secrets.get("access", {})
    except StreamlitSecretNotFoundError:
        return {}
    if not isinstance(access_config, Mapping):
        raise ValueError("[access] must be a mapping.")
    return access_config


def _normalize_team_id(team_id):
    team_id = str(team_id).strip()
    if not team_id.isdigit() or int(team_id) < 1:
        raise ValueError("CBS team IDs must be positive numbers.")
    return team_id


def _hash_code(code):
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def get_cbs_code_mapping():
    access_config = _get_access_config()
    configured_codes = access_config.get("team_access_codes", [])
    if not isinstance(configured_codes, list):
        raise ValueError("[access].team_access_codes must be a list.")

    mapping = {}
    for entry in configured_codes:
        if not isinstance(entry, Mapping):
            raise ValueError("Each CBS access code entry must be a mapping.")
        code = entry.get("code")
        if not isinstance(code, str) or len(code) < 20:
            raise ValueError(
                "Each CBS access code must be a string of at least 20 characters."
            )
        team_id = _normalize_team_id(entry.get("team_id", ""))
        code_hash = _hash_code(code)
        if code_hash in mapping:
            raise ValueError("CBS access codes must be unique.")
        mapping[code_hash] = team_id
    return mapping


def _find_team_for_code(code, code_mapping):
    if not isinstance(code, str) or not code:
        return None
    submitted_hash = _hash_code(code)
    for known_hash, team_id in code_mapping.items():
        if hmac.compare_digest(submitted_hash, known_hash):
            return team_id
    return None


def _find_team_for_code_hash(code_hash, code_mapping):
    if not isinstance(code_hash, str):
        return None
    for known_hash, team_id in code_mapping.items():
        if hmac.compare_digest(code_hash, known_hash):
            return team_id
    return None


def get_authenticated_cbs_team_id():
    code_mapping = get_cbs_code_mapping()
    authenticated_hash = st.session_state.get(SESSION_CODE_HASH_KEY)
    return _find_team_for_code_hash(authenticated_hash, code_mapping)


def _sign_out():
    st.session_state.pop(SESSION_CODE_HASH_KEY, None)


def require_site_access():
    try:
        code_mapping = get_cbs_code_mapping()
    except ValueError as exc:
        st.error(f"Site access configuration is invalid: {exc}")
        return False

    if not code_mapping:
        st.error(
            "Site access is not configured. Add individual CBS team access "
            "codes to `[access].team_access_codes` in Streamlit secrets."
        )
        return False

    authenticated_hash = st.session_state.get(SESSION_CODE_HASH_KEY)
    if _find_team_for_code_hash(authenticated_hash, code_mapping):
        st.sidebar.button("Sign out", on_click=_sign_out)
        return True

    if authenticated_hash:
        _sign_out()

    st.title("CBS League Sign In")
    st.write("Enter the individual access code provided by your league administrator.")
    with st.form("cbs_access_code_login"):
        submitted_code = st.text_input("CBS team access code", type="password")
        submitted = st.form_submit_button("Continue")

    if submitted:
        team_id = _find_team_for_code(submitted_code, code_mapping)
        if team_id is None:
            st.error("That access code is not valid.")
            return False

        st.session_state[SESSION_CODE_HASH_KEY] = _hash_code(submitted_code)
        st.rerun()
        return False

    return False
