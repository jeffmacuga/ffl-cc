import os

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError


def _get_credential(name):
    try:
        value = st.secrets.get(name)
    except StreamlitSecretNotFoundError:
        value = None
    return str(value or os.environ.get(name, "")).strip()


ESPN_SWID = _get_credential("ESPN_SWID")
ESPN_S2 = _get_credential("ESPN_S2")
FANTASYPROS_API_KEY = _get_credential("FANTASYPROS_API_KEY")

LEAGUES = [
    {
        "name": "Kick-Butt Football",
        "platform": "ESPN",
        "league_id": 465649962,
        "year": 2026,
        "swid": ESPN_SWID,
        "espn_s2": ESPN_S2
    },
    {
        "name": "AFS",
        "platform": "ESPN",
        "league_id": 1205232556,
        "year": 2026,
        "swid": ESPN_SWID,
        "espn_s2": ESPN_S2
    },
    {
        "name": "CBS",
        "platform": "CBS"
    }
]

def set_streamlit_config():
    st.set_page_config(page_title="Fantasy Command Center", layout="wide")
