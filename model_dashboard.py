import streamlit as st
import pandas as pd
import math
import json
import os
from datetime import datetime, date

LOG_FILE = "model_log.json"

def load_log():
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r") as f:
                return json.load(f)
        except:
            return {"picks": [], "slips": []}
    return {"picks": [], "slips": []}

def save_log(data):
    try:
        with open(LOG_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except:
        pass

def norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))

def run_game(row):
    prior = float(row.get("prior_net_rating", 0) or 0)
    recent = float(row.get("recent_form", 0) or 0)
    home = float(row.get("home_court", 0) or 0)
    injury = float(row.get("injury_adj", 0) or 0)
    rest = float(row.get("rest_adj", 0) or 0)
    market_p = float(row.get("market_prob", 0.5) or 0.5)
    posterior = 0.55 * prior + 0.35 * recent + home + injury + rest
    model_prob = min(0.86, max(0.50, 0.50 + norm_cdf(posterior / 11) * 0.36))
    edge = round(model_prob - market_p, 3)
    fav = str(row.get("favorite", "") or row.get("matchup", "").split(" vs ")[0]).strip()
    if edge >= 0.02 and posterior >= 4:
        regular = f"{fav} -{round(posterior - 1.5, 1)}"
        safe = f"{fav} -{round(max(1.5, posterior - 3.5), 1)}"
    elif edge >= 0.015:
        regular = f"{fav} ML"
        safe = f"{fav} ML"
    else:
        regular = safe = "Pass"
    return {"model_prob": round(model_prob, 3), "edge": edge, "regular": regular, "safe": safe,
            "detail": f"Proj margin {round(posterior,1)}"}

def run_prop(row):
    proj = float(row.get("projection", 0) or 0)
    line = float(row.get("line", 0) or 0)
    market_p = float(row.get("market_prob", 0.5) or 0.5)
    std = float(row.get("std_dev", 0) or max(proj * 0.22, 1))
    hit_rate = float(row.get("season_hit_rate", 0.5) or 0.5)
    opp_adj = float(row.get("opponent_adj", 0) or 0)
    adj = proj + opp_adj
    diff = adj - line
    model_prob = min(0.83, max(0.50, 0.62 * norm_cdf(diff / std) + 0.38 * hit_rate))
    edge = round(model_prob - market_p, 3)
    direction = "Over" if diff >= 0 else "Under"
    if edge >= 0.025:
        regular = f"{direction} {line}"
        step = 10 if line >= 100 else 5 if line >= 25 else 2
        safe_line = round(line - step if direction == "Over" else line + step, 1)
        safe = f"{direction} {safe_line}"
    else:
        regular = safe = "Pass"
    return {"model_prob": round(model_prob, 3), "edge": edge, "regular": regular, "safe": safe,
            "detail": f"{row.get('prop_type','')} (adj {round(adj,1)})"}

# ---------- UI ----------
st.set_page_config(page_title="Model Dashboard", page_icon="📊", layout="wide")
st.markdown("""
<style>
    .big-title {font-size: 2.4rem; font-weight: 700; margin-bottom: 0.2rem;}
    .subtitle {color: #888; margin-bottom: 1.5rem;}
    .slip-box {background: #1e1e1e; padding: 1rem; border-radius: 8px; border-left: 4px solid #00c853;}
</style>
""", unsafe_allow_html=True)

st.markdown('<p class="big-title">Sports Model Dashboard</p>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Bayesian projections · Edge filtering · Calibration tracking</p>', unsafe_allow_html=True)

if "log" not in st.session_state:
    st.session_state.log = load_log()

tab1, tab2, tab3 = st.tabs(["Run Slate", "Calibration", "Log"])

with tab1:
    st.subheader("Quick Start")
    if st.button("Download Today's Sample CSVs"):
        games_csv = """matchup,favorite,prior_net_rating,recent_form,home_court,injury_adj,rest_adj,market_prob
Pistons vs Wizards,Pistons,7.9,6.5,2.5,0.5,0,0.52
Cavaliers vs Hornets,Cavaliers,4.8,5.2,2.5,1.0,0,0.55
Lakers vs Hawks,Hawks,3.1,4.0,2.0,0,0,0.48
Bills vs Vikings,Bills,3.8,2.5,-1.0,0.5,0,0.54"""
        props_csv = """player,prop_type,projection,line,std_dev,season_hit_rate,opponent_adj,market_prob,matchup
Cade Cunningham,Points,24.8,22.5,5.5,0.58,1.2,0.52,Pistons vs Wizards
Cade Cunningham,Assists,8.1,7.5,2.4,0.60,0.4,0.50,Pistons vs Wizards
Josh Allen,Passing Yards,246,230.5,42,0.57,4,0.53,Bills vs Vikings
James Cook,Rushing Yards,79,70.5,20,0.61,2,0.51,Bills vs Vikings"""
        st.download_button("Download Games CSV", games_csv, "today_games.csv", "text/csv")
        st.download_button("Download Props CSV", props_csv, "today_props.csv", "text/csv")
        st.caption("Edit the numbers, then re-upload below.")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Game Lines CSV")
        game_file = st.file_uploader("Games", type="csv", key="games")
    with c2:
        st.subheader("Player Props CSV")
        prop_file = st.file_uploader("Props", type="csv", key="props")

    if st.button("Generate Slips", type="primary"):
        all_plays = []

        if game_file:
            gdf = pd.read_csv(game_file)
            for _, row in gdf.iterrows():
                if pd.notna(row.get("prior_net_rating")):
                    r = run_game(row)
                    if r["regular"] != "Pass":
                        all_plays.append({"type": "Game", "name": row.get("matchup"), **r})

        if prop_file:
            pdf = pd.read_csv(prop_file)
            for _, row in pdf.iterrows():
                if pd.notna(row.get("projection")):
                    r = run_prop(row)
                    if r["regular"] != "Pass":
                        all_plays.append({"type": "Prop", "name": f"{row.get('player')} {row.get('prop_type')}", **r})

        if all_plays:
            plays_df = pd.DataFrame(all_plays).sort_values("edge", ascending=False)
            st.subheader("All Qualifying Plays")
            st.dataframe(plays_df[["type", "name", "detail", "model_prob", "edge", "regular", "safe"]], use_container_width=True)

            top = plays_df.head(5)
            st.markdown("### Today’s Slip")
            st.markdown('<div class="slip-box">', unsafe_allow_html=True)
            for _, p in top.iterrows():
                st.markdown(f"**{p['regular']}** · {p['name']} · {p['model_prob']*100:.0f}%")
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown("### Safe Slip")
            st.markdown('<div class="slip-box">', unsafe_allow_html=True)
            for _, p in top.iterrows():
                st.markdown(f"**{p['safe']}** · {p['name']}")
            st.markdown('</div>', unsafe_allow_html=True)

            # Log it
            slip_record = {"date": date.today().isoformat(), "plays": top.to_dict("records"), "ts": datetime.now().isoformat()}
            st.session_state.log["slips"].append(slip_record)
            save_log(st.session_state.log)
        else:
            st.info("Upload at least one CSV with valid rows.")

with tab2:
    st.subheader("Calibration")
    settled = [p for p in st.session_state.log.get("picks", []) if p.get("result")]
    if settled:
        hits = sum(1 for p in settled if p["result"] == "Hit")
        st.metric("Settled", f"{hits}-{len(settled)-hits}", f"{hits/len(settled)*100:.1f}%")
    else:
        st.info("No settled picks yet. Log results in the Log tab.")

with tab3:
    st.subheader("Pick Log")
    if st.session_state.log.get("slips"):
        st.write(f"Slips generated: {len(st.session_state.log['slips'])}")
    st.caption("Manual result entry can be added here as volume grows.")

st.sidebar.markdown("### CSV Formats")
st.sidebar.markdown("**Games:** matchup, favorite, prior_net_rating, recent_form, home_court, injury_adj, rest_adj, market_prob")
st.sidebar.markdown("**Props:** player, prop_type, projection, line, std_dev, season_hit_rate, opponent_adj, market_prob, matchup")
st.sidebar.caption("Safe lines use fixed steps. Match to Kalshi.")

