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

def apply_pillars(row, is_prop=False):
    """Basic pillar adjustments. Returns adjusted values and flags."""
    flags = []
    mult = 1.0

    # Injury pillar
    if str(row.get("key_injury", "")).lower() in ["out", "yes", "1"]:
        mult *= 0.85
        flags.append("Injury")

    # Rest pillar
    days_rest = float(row.get("days_rest", 2) or 2)
    if days_rest <= 1:
        mult *= 0.90
        flags.append("Short rest")

    # Form disagreement
    if not is_prop:
        prior = float(row.get("prior_net_rating", 0) or 0)
        recent = float(row.get("recent_form", 0) or 0)
        if abs(prior - recent) > 6:
            mult *= 0.92
            flags.append("Form split")

    return mult, flags

def run_game(row):
    prior = float(row.get("prior_net_rating", 0) or 0)
    recent = float(row.get("recent_form", 0) or 0)
    home = float(row.get("home_court", 0) or 0)
    injury = float(row.get("injury_adj", 0) or 0)
    rest = float(row.get("rest_adj", 0) or 0)
    market_p = float(row.get("market_prob", 0.5) or 0.5)

    mult, flags = apply_pillars(row, is_prop=False)
    posterior = (0.55 * prior + 0.35 * recent + home + injury + rest) * mult
    model_prob = min(0.86, max(0.48, 0.50 + norm_cdf(posterior / 11) * 0.36))
    edge = round(model_prob - market_p, 3)

    fav = str(row.get("favorite", "") or str(row.get("matchup", "")).split(" vs ")[0]).strip()
    if edge >= 0.02 and posterior >= 3.5 and "Injury" not in flags:
        regular = f"{fav} -{round(max(1, posterior - 1.5), 1)}"
        safe = f"{fav} -{round(max(1, posterior - 3.5), 1)}" if posterior >= 6 else f"{fav} ML"
    elif edge >= 0.015 and "Injury" not in flags:
        regular = f"{fav} ML"
        safe = f"{fav} ML"
    else:
        regular = safe = "Pass"

    return {"model_prob": round(model_prob, 3), "edge": edge, "regular": regular, "safe": safe,
            "detail": f"Margin {round(posterior,1)}", "flags": ", ".join(flags) or "—"}

def run_prop(row):
    proj = float(row.get("projection", 0) or 0)
    line = float(row.get("line", 0) or 0)
    market_p = float(row.get("market_prob", 0.5) or 0.5)
    std = float(row.get("std_dev", 0) or max(proj * 0.22, 1))
    hit_rate = float(row.get("season_hit_rate", 0.5) or 0.5)
    opp_adj = float(row.get("opponent_adj", 0) or 0)

    mult, flags = apply_pillars(row, is_prop=True)
    adj = (proj + opp_adj) * mult
    diff = adj - line
    model_prob = min(0.83, max(0.48, 0.62 * norm_cdf(diff / std) + 0.38 * hit_rate))
    edge = round(model_prob - market_p, 3)
    direction = "Over" if diff >= 0 else "Under"

    if edge >= 0.025 and "Injury" not in flags:
        regular = f"{direction} {line}"
        step = 10 if line >= 100 else 5 if line >= 25 else 2
        safe_line = round(line - step if direction == "Over" else line + step, 1)
        safe = f"{direction} {safe_line}"
    else:
        regular = safe = "Pass"

    return {"model_prob": round(model_prob, 3), "edge": edge, "regular": regular, "safe": safe,
            "detail": f"{row.get('prop_type','')} (adj {round(adj,1)})", "flags": ", ".join(flags) or "—"}

st.set_page_config(page_title="Model Dashboard", page_icon="📊", layout="wide")
st.markdown("""
<style>
.big-title {font-size:2.2rem; font-weight:700;}
.slip-box {background:#1a1a1a; padding:1rem; border-radius:8px; border-left:4px solid #00c853; margin:0.5rem 0;}
</style>
""", unsafe_allow_html=True)
st.markdown('<p class="big-title">Sports Model Dashboard</p>', unsafe_allow_html=True)

if "log" not in st.session_state:
    st.session_state.log = load_log()

tab1, tab2 = st.tabs(["Run Slate", "Log"])

with tab1:
    if st.button("Download Sample CSVs"):
        st.download_button("Games CSV", open("today_games.csv").read() if os.path.exists("today_games.csv") else "matchup,favorite,prior_net_rating,recent_form,home_court,injury_adj,rest_adj,key_injury,days_rest,market_prob\n", "today_games.csv")
        st.download_button("Props CSV", open("today_props.csv").read() if os.path.exists("today_props.csv") else "player,prop_type,projection,line,std_dev,season_hit_rate,opponent_adj,key_injury,market_prob,matchup\n", "today_props.csv")

    c1, c2 = st.columns(2)
    with c1:
        game_file = st.file_uploader("Game Lines CSV", type="csv")
    with c2:
        prop_file = st.file_uploader("Player Props CSV", type="csv")

    if st.button("Generate Slips", type="primary"):
        plays = []
        if game_file:
            for _, row in pd.read_csv(game_file).iterrows():
                if pd.notna(row.get("prior_net_rating")):
                    r = run_game(row)
                    if r["regular"] != "Pass":
                        plays.append({"type": "Game", "name": row.get("matchup"), **r})
        if prop_file:
            for _, row in pd.read_csv(prop_file).iterrows():
                if pd.notna(row.get("projection")):
                    r = run_prop(row)
                    if r["regular"] != "Pass":
                        plays.append({"type": "Prop", "name": f"{row.get('player')} {row.get('prop_type')}", **r})

        if plays:
            df = pd.DataFrame(plays).sort_values("edge", ascending=False)
            st.dataframe(df[["type","name","detail","model_prob","edge","regular","safe","flags"]], use_container_width=True)
            top = df.head(5)
            st.markdown("### Today’s Slip")
            for _, p in top.iterrows():
                st.markdown(f"**{p['regular']}** · {p['name']} · {p['model_prob']*100:.0f}%")
            st.markdown("### Safe Slip")
            for _, p in top.iterrows():
                st.markdown(f"**{p['safe']}** · {p['name']}")
            st.session_state.log["slips"].append({"date": str(date.today()), "count": len(top)})
            save_log(st.session_state.log)
        else:
            st.info("No qualifying plays. Check inputs or flags.")

with tab2:
    st.write(f"Slips logged: {len(st.session_state.log.get('slips', []))}")
    st.caption("Pillar flags (Injury, Short rest, Form split) reduce edge or cause a Pass.")

st.sidebar.markdown("### New Flag Columns")
st.sidebar.markdown("- **key_injury**: `out` or `yes` if main player is out")
st.sidebar.markdown("- **days_rest**: 0 or 1 for back-to-back")
