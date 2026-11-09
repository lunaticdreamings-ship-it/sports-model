import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime, date

# File for persistence - works locally and on Streamlit Cloud
LOG_FILE = "model_dashboard_log.json"

def load_log():
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r") as f:
                return json.load(f)
        except:
            return {"picks": [], "calibration": [], "daily_slips": [], "slate": {}, "api_keys": {}}
    return {"picks": [], "calibration": [], "daily_slips": [], "slate": {}, "api_keys": {}}

def save_log(data):
    try:
        with open(LOG_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        st.warning(f"Could not save log: {e}")

DEFAULT_SLATE = {s: [] for s in ["NBA", "NFL", "NHL", "MLB", "Soccer", "Tennis"]}

if "log" not in st.session_state:
    st.session_state.log = load_log()
    if "slate" not in st.session_state.log:
        st.session_state.log["slate"] = DEFAULT_SLATE.copy()
    if "api_keys" not in st.session_state.log:
        st.session_state.log["api_keys"] = {}

st.set_page_config(page_title="Model Dashboard", layout="wide")
st.title("Personal Sports Model Dashboard")

# Sidebar
st.sidebar.header("Manual Pick")
sport = st.sidebar.selectbox("Sport", ["NBA", "NFL", "NHL", "MLB", "Soccer", "Tennis"])
matchup = st.sidebar.text_input("Matchup")
lean = st.sidebar.text_input("Lean")
model_prob = st.sidebar.slider("Model Probability (%)", 50, 90, 65)
market_prob = st.sidebar.slider("Market Implied Probability (%)", 40, 80, 52)
notes = st.sidebar.text_area("Notes")

if st.sidebar.button("Log Pick"):
    pick = {
        "timestamp": datetime.now().isoformat(),
        "sport": sport,
        "matchup": matchup,
        "lean": lean,
        "model_prob": model_prob / 100,
        "market_prob": market_prob / 100,
        "edge": (model_prob - market_prob) / 100,
        "notes": notes,
        "result": None
    }
    st.session_state.log["picks"].append(pick)
    save_log(st.session_state.log)
    st.sidebar.success("Pick logged")

st.sidebar.markdown("---")
st.sidebar.subheader("API Keys (Optional)")
odds_key = st.sidebar.text_input("Odds API Key", value=st.session_state.log["api_keys"].get("odds", ""), type="password")
if st.sidebar.button("Save API Key"):
    st.session_state.log["api_keys"]["odds"] = odds_key
    save_log(st.session_state.log)
    st.sidebar.success("Saved")

# Tabs
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Daily Runner", "Slate Editor", "Live Data", "Projection", "Logged Picks", "Calibration"])

with tab1:
    st.subheader("Daily Slip Generator")
    today = date.today().isoformat()
    st.write(f"**Date:** {today}")

    available = [s for s, games in st.session_state.log.get("slate", {}).items() if games]
    selected = st.multiselect("Sports with Games", available, default=available)
    min_edge = st.slider("Minimum Model Edge", 0.0, 0.20, 0.03, 0.01)
    max_legs = st.slider("Max Legs per Slip", 3, 8, 5)

    if st.button("Run Daily Slips", type="primary"):
        regular, safe = [], []
        for s in selected:
            for game in st.session_state.log["slate"].get(s, []):
                edge = game.get("model_prob", 0) - game.get("market_prob", 0)
                if edge >= min_edge and len(regular) < max_legs:
                    regular.append({
                        "sport": s, "matchup": game["matchup"], "lean": game["lean"],
                        "prob": round(game["model_prob"], 3), "edge": round(edge, 3)
                    })
                    safe.append({
                        "sport": s, "matchup": game["matchup"], "lean": game.get("safe", game["lean"]),
                        "prob": round(game["model_prob"] + 0.02, 3), "edge": round(edge + 0.01, 3)
                    })

        slip = {"date": today, "regular": regular, "safe": safe, "generated_at": datetime.now().isoformat()}
        st.session_state.log["daily_slips"].append(slip)
        save_log(st.session_state.log)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### Regular Slip")
            st.dataframe(pd.DataFrame(regular) if regular else pd.DataFrame(), use_container_width=True)
        with c2:
            st.markdown("### Safe Slip")
            st.dataframe(pd.DataFrame(safe) if safe else pd.DataFrame(), use_container_width=True)

    if st.session_state.log.get("daily_slips"):
        st.subheader("Recent Daily Slips")
        for slip in reversed(st.session_state.log["daily_slips"][-3:]):
            with st.expander(f"{slip['date']} ({len(slip['regular'])} legs)"):
                st.dataframe(pd.DataFrame(slip["regular"]) if slip["regular"] else pd.DataFrame())
                st.dataframe(pd.DataFrame(slip["safe"]) if slip["safe"] else pd.DataFrame())

with tab2:
    st.subheader("Slate Editor")
    edit_sport = st.selectbox("Sport to Edit", ["NBA", "NFL", "NHL", "MLB", "Soccer", "Tennis"])
    current = st.session_state.log["slate"].get(edit_sport, [])
    if current:
        st.dataframe(pd.DataFrame(current), use_container_width=True)
    else:
        st.info(f"No games for {edit_sport}.")

    st.markdown("**Add Game**")
    c1, c2, c3 = st.columns(3)
    with c1:
        new_matchup = st.text_input("Matchup", key="mu")
        new_lean = st.text_input("Regular Lean", key="ln")
    with c2:
        new_safe = st.text_input("Safe Lean", key="sf")
        new_model = st.number_input("Model Prob", 0.50, 0.90, 0.70, 0.01, key="mp")
    with c3:
        new_market = st.number_input("Market Prob", 0.40, 0.80, 0.55, 0.01, key="mk")
        if st.button("Add to Slate"):
            game = {"matchup": new_matchup, "lean": new_lean, "safe": new_safe or new_lean,
                    "model_prob": new_model, "market_prob": new_market}
            st.session_state.log["slate"].setdefault(edit_sport, []).append(game)
            save_log(st.session_state.log)
            st.rerun()

    if st.button("Clear Sport"):
        st.session_state.log["slate"][edit_sport] = []
        save_log(st.session_state.log)
        st.rerun()

with tab3:
    st.subheader("Live Data Integration")
    st.info("Upload a CSV to load games into the slate.")

    uploaded = st.file_uploader("Upload Slate CSV", type="csv")
    if uploaded:
        df = pd.read_csv(uploaded)
        st.dataframe(df)
        if st.button("Load CSV into Slate"):
            for _, row in df.iterrows():
                s = row.get("sport", "NBA")
                game = {
                    "matchup": row.get("matchup", ""),
                    "lean": row.get("lean", ""),
                    "safe": row.get("safe", row.get("lean", "")),
                    "model_prob": float(row.get("model_prob", 0.65)),
                    "market_prob": float(row.get("market_prob", 0.55))
                }
                st.session_state.log["slate"].setdefault(s, []).append(game)
            save_log(st.session_state.log)
            st.success("CSV loaded into slate")
            st.rerun()

with tab4:
    st.subheader("Quick Projection Tool")
    col1, col2 = st.columns(2)
    with col1:
        prior = st.number_input("Prior Net Rating / Edge", value=7.9, step=0.1)
        recent = st.number_input("Recent Form Edge", value=6.0, step=0.1)
        prior_weight = st.slider("Weight on Prior", 0.0, 1.0, 0.6)
    with col2:
        home_court = st.number_input("Home Court / Rest Adj", value=2.5, step=0.1)
        matchup_adj = st.number_input("Matchup Adjustment", value=1.5, step=0.1)
        market_line = st.number_input("Market Line", value=-10.5, step=0.5)

    posterior = (prior_weight * prior) + ((1 - prior_weight) * recent) + home_court + matchup_adj
    st.metric("Posterior Projected Margin", f"{posterior:.1f}")

    import math
    def norm_cdf(x, mu=0, sigma=11):
        return 0.5 * (1 + math.erf((x - mu) / (sigma * math.sqrt(2))))
    cover_prob = 1 - norm_cdf(abs(market_line), mu=posterior, sigma=11)
    st.metric("Estimated Cover Probability", f"{cover_prob*100:.1f}%")

with tab5:
    st.subheader("Logged Picks")
    if st.session_state.log["picks"]:
        df = pd.DataFrame(st.session_state.log["picks"])
        st.dataframe(df[["timestamp", "sport", "matchup", "lean", "model_prob", "market_prob", "edge", "result"]], use_container_width=True)
        pick_idx = st.selectbox("Select Pick", range(len(st.session_state.log["picks"])),
                                 format_func=lambda i: f"{st.session_state.log['picks'][i]['matchup']} - {st.session_state.log['picks'][i]['lean']}")
        result = st.radio("Result", ["Hit", "Miss"], horizontal=True)
        if st.button("Update Result"):
            st.session_state.log["picks"][pick_idx]["result"] = result
            save_log(st.session_state.log)
            st.rerun()
    else:
        st.info("No picks logged yet.")

with tab6:
    st.subheader("Calibration")
    settled = [p for p in st.session_state.log["picks"] if p["result"] is not None]
    if settled:
        hits = sum(1 for p in settled if p["result"] == "Hit")
        total = len(settled)
        st.metric("Settled Record", f"{hits}-{total-hits} ({hits/total*100:.1f}%)")
        buckets = {"50-60%": [], "60-70%": [], "70-80%": [], "80%+": []}
        for p in settled:
            prob = p["model_prob"]
            key = "50-60%" if prob < 0.6 else "60-70%" if prob < 0.7 else "70-80%" if prob < 0.8 else "80%+"
            buckets[key].append(p)
        cal_data = [{"Bucket": b, "Picks": len(ps), "Hit Rate": f"{sum(1 for p in ps if p['result']=='Hit')/len(ps)*100:.1f}%"}
                    for b, ps in buckets.items() if ps]
        if cal_data:
            st.dataframe(pd.DataFrame(cal_data), use_container_width=True)
    else:
        st.info("No settled picks yet.")

st.sidebar.markdown("---")
st.sidebar.caption("Personal dashboard.")
