import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime, date

LOG_FILE = "model_dashboard_log.json"

def load_log():
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r") as f:
                return json.load(f)
        except:
            return {"picks": [], "daily_slips": [], "slate": {}}
    return {"picks": [], "daily_slips": [], "slate": {}}

def save_log(data):
    try:
        with open(LOG_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except:
        pass

# Sample data - replace with live pull
SAMPLE = {
    "NBA": [
        {"matchup": "Pistons vs Wizards", "lean": "Pistons -7.5", "prob": 0.74},
        {"matchup": "Cavaliers vs Hornets", "lean": "Cavaliers -5.5", "prob": 0.73},
    ],
    "NFL": [
        {"matchup": "Bills vs Vikings", "lean": "Bills ML", "prob": 0.72},
    ],
    "NHL": [],
    "MLB": [],
    "Soccer": [],
    "Tennis": []
}

if "log" not in st.session_state:
    st.session_state.log = load_log()

st.set_page_config(page_title="Model Dashboard", layout="wide")
st.title("Personal Sports Model Dashboard")

st.header("Run Today's Slate")
sport = st.selectbox("Select Sport", ["NBA", "NFL", "NHL", "MLB", "Soccer", "Tennis"])

if st.button("Run Slate", type="primary"):
    games = SAMPLE.get(sport, [])
    if not games:
        st.warning(f"No sample data loaded for {sport}. Add games in the editor or connect a live feed.")
    else:
        # Sort by probability and take top
        games = sorted(games, key=lambda x: x["prob"], reverse=True)[:5]
        slip = {
            "date": date.today().isoformat(),
            "sport": sport,
            "legs": games,
            "generated_at": datetime.now().isoformat()
        }
        st.session_state.log["daily_slips"].append(slip)
        save_log(st.session_state.log)

        st.success(f"Generated {len(games)}-leg slip for {sport}")
        st.dataframe(pd.DataFrame(games), use_container_width=True)

st.markdown("---")
st.subheader("Recent Slips")
if st.session_state.log.get("daily_slips"):
    for slip in reversed(st.session_state.log["daily_slips"][-5:]):
        with st.expander(f"{slip['date']} - {slip['sport']} ({len(slip['legs'])} legs)"):
            st.dataframe(pd.DataFrame(slip["legs"]), use_container_width=True)
else:
    st.info("No slips generated yet.")

st.sidebar.header("Add / Edit Games")
st.sidebar.caption("Use this until live data is connected.")
edit_sport = st.sidebar.selectbox("Sport", ["NBA", "NFL", "NHL", "MLB", "Soccer", "Tennis"], key="es")
mu = st.sidebar.text_input("Matchup")
ln = st.sidebar.text_input("Lean")
pr = st.sidebar.number_input("Probability", 0.5, 0.9, 0.7, 0.01)
if st.sidebar.button("Add Game"):
    SAMPLE.setdefault(edit_sport, []).append({"matchup": mu, "lean": ln, "prob": pr})
    st.sidebar.success("Added (session only)")
