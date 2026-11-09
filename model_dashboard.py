import streamlit as st
import pandas as pd
import json
import os
import requests
from datetime import datetime, date

LOG_FILE = "model_dashboard_log.json"

def load_log():
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r") as f:
                return json.load(f)
        except:
            return {"picks": [], "daily_slips": [], "slate": []}
    return {"picks": [], "daily_slips": [], "slate": []}

def save_log(data):
    try:
        with open(LOG_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except:
        pass

def fetch_kalshi_markets(sport_keyword):
    try:
        url = "https://api.elections.kalshi.com/trade-api/v2/markets"
        params = {"limit": 50, "status": "open"}
        r = requests.get(url, params=params, timeout=8)
        if r.status_code != 200:
            return []
        markets = r.json().get("markets", [])
        results = []
        for m in markets:
            title = (m.get("title", "") + " " + m.get("subtitle", "")).strip()
            if sport_keyword.lower() in title.lower():
                price = m.get("yes_ask") or m.get("last_price") or 50
                results.append({
                    "matchup": title[:90],
                    "market_prob": round(price / 100 if price > 1 else price, 3)
                })
        return results[:6]
    except:
        return []

if "log" not in st.session_state:
    st.session_state.log = load_log()

st.set_page_config(page_title="Model Dashboard", layout="wide")
st.title("Personal Sports Model Dashboard")

tab1, tab2 = st.tabs(["Run Slate", "Upload CSV"])

with tab1:
    st.header("Run Today's Slate")
    sport = st.selectbox("Select Sport", ["NBA", "NFL", "NHL", "MLB", "Soccer", "Tennis"])
    if st.button("Run Slate", type="primary"):
        with st.spinner("Pulling data..."):
            data = fetch_kalshi_markets(sport)
            if data:
                st.success(f"Found {len(data)} markets")
                st.dataframe(pd.DataFrame(data), use_container_width=True)
            else:
                st.warning("No markets found. Try uploading a CSV instead.")

with tab2:
    st.header("Upload Slate CSV")
    st.caption("Upload the CSV from the scraper. It should have columns: sport, matchup")
    uploaded = st.file_uploader("Choose CSV", type="csv")
    if uploaded:
        df = pd.read_csv(uploaded)
        st.dataframe(df, use_container_width=True)
        if st.button("Load into Slate"):
            st.session_state.log["slate"] = df.to_dict("records")
            save_log(st.session_state.log)
            st.success(f"Loaded {len(df)} games")
            st.rerun()

    if st.session_state.log.get("slate"):
        st.subheader("Current Loaded Slate")
        st.dataframe(pd.DataFrame(st.session_state.log["slate"]), use_container_width=True)

st.sidebar.markdown("### Quick Guide")
st.sidebar.markdown("1. Run the scraper on your computer")
st.sidebar.markdown("2. Upload the CSV here")
st.sidebar.markdown("3. Or use Run Slate for Kalshi markets")
