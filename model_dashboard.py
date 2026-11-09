import streamlit as st
import pandas as pd
import json
import os
import math
from datetime import datetime, date

LOG_FILE = "model_dashboard_log.json"

def load_log():
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r") as f:
                return json.load(f)
        except:
            return {"slips": []}
    return {"slips": []}

def save_log(data):
    try:
        with open(LOG_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except:
        pass

def norm_cdf(x, mu=0, sigma=1):
    return 0.5 * (1 + math.erf((x - mu) / (sigma * math.sqrt(2))))

def run_game(row):
    prior = float(row.get("prior_net_rating", 0) or 0)
    recent = float(row.get("recent_form", 0) or 0)
    home = float(row.get("home_court", 0) or 0)
    injury = float(row.get("injury_adj", 0) or 0)
    market_p = float(row.get("market_prob", 0.5) or 0.5)
    rest = float(row.get("rest_adj", 0) or 0)

    posterior = (0.55 * prior) + (0.35 * recent) + home + injury + rest
    cover_prob = norm_cdf(posterior / 11)
    model_prob = min(0.87, max(0.50, 0.5 + cover_prob * 0.4))
    edge = round(model_prob - market_p, 3)

    if posterior >= 7:
        reg = round(posterior - 2, 1)
        safe = round(posterior - 4, 1)
        regular = f"-{reg}"
        safe_line = f"-{max(1, safe)}"
    elif posterior >= 3:
        regular = f"-{round(posterior - 1.5, 1)}"
        safe_line = "ML"
    else:
        regular = "ML"
        safe_line = "ML"

    return {
        "posterior": round(posterior, 1),
        "model_prob": round(model_prob, 3),
        "edge": edge,
        "regular": regular if edge >= 0.02 else "Pass",
        "safe": safe_line if edge >= 0.02 else "Pass"
    }

def run_prop(row):
    proj = float(row.get("projection", 0) or 0)
    line = float(row.get("line", 0) or 0)
    market_p = float(row.get("market_prob", 0.5) or 0.5)
    std = float(row.get("std_dev", 0) or (proj * 0.25))  # default 25% of projection
    hit_rate = float(row.get("season_hit_rate", 0.5) or 0.5)
    opp_adj = float(row.get("opponent_adj", 0) or 0)

    adj_proj = proj + opp_adj
    diff = adj_proj - line
    z = diff / std if std > 0 else 0
    raw_prob = norm_cdf(z)
    # Blend with season hit rate
    model_prob = min(0.84, max(0.48, (0.7 * raw_prob) + (0.3 * hit_rate)))
    edge = round(model_prob - market_p, 3)

    direction = "Over" if diff > 0 else "Under"
    if edge >= 0.035:
        regular = f"{direction} {line}"
        safe_shift = 1.5 if abs(diff) > 3 else 1
        safe_line = line - safe_shift if diff > 0 else line + safe_shift
        safe = f"{direction} {safe_line}"
    elif edge >= 0.015:
        regular = f"{direction} {line} (thin)"
        safe = "Pass or reduce"
    else:
        regular = "Pass"
        safe = "Pass"

    return {
        "adj_projection": round(adj_proj, 1),
        "model_prob": round(model_prob, 3),
        "edge": edge,
        "regular": regular,
        "safe": safe
    }

if "log" not in st.session_state:
    st.session_state.log = load_log()

st.set_page_config(page_title="Model Dashboard", layout="wide")
st.title("Personal Sports Model Dashboard")

st.header("Upload Input CSV")
with st.expander("Column Guide"):
    st.markdown("**Games:** sport, matchup, prior_net_rating, recent_form, home_court, injury_adj, rest_adj, market_prob")
    st.markdown("**Props:** sport, player, prop_type, projection, line, std_dev, season_hit_rate, opponent_adj, market_prob, matchup")

uploaded = st.file_uploader("Upload CSV", type="csv")
if uploaded:
    df = pd.read_csv(uploaded)
    st.dataframe(df, use_container_width=True)

    if st.button("Run Model", type="primary"):
        results = []
        for _, row in df.iterrows():
            is_prop = "projection" in df.columns and pd.notna(row.get("projection"))
            if is_prop:
                c = run_prop(row)
                results.append({
                    "sport": row.get("sport", ""),
                    "matchup": row.get("matchup", ""),
                    "player": row.get("player", ""),
                    "type": "Prop",
                    "detail": f"{row.get('prop_type','')} (proj {c['adj_projection']})",
                    "model_prob": c["model_prob"],
                    "edge": c["edge"],
                    "regular": c["regular"],
                    "safe": c["safe"]
                })
            else:
                c = run_game(row)
                results.append({
                    "sport": row.get("sport", ""),
                    "matchup": row.get("matchup", ""),
                    "player": "",
                    "type": "Game",
                    "detail": f"Margin {c['posterior']}",
                    "model_prob": c["model_prob"],
                    "edge": c["edge"],
                    "regular": c["regular"],
                    "safe": c["safe"]
                })

        out = pd.DataFrame(results)
        plays = out[out["edge"] >= 0.02].sort_values("edge", ascending=False)

        st.subheader("All Results")
        st.dataframe(out, use_container_width=True)
        st.subheader("Recommended (Edge ≥ 2%)")
        if len(plays):
            st.dataframe(plays, use_container_width=True)
        else:
            st.info("No plays ≥ 2% edge.")

st.sidebar.markdown("### New Prop Fields")
st.sidebar.markdown("- **std_dev**: Typical variation (default 25% of projection)")
st.sidebar.markdown("- **season_hit_rate**: How often player clears similar lines (0-1)")
st.sidebar.markdown("- **opponent_adj**: Plus/minus vs this defense")
st.sidebar.markdown("- **rest_adj**: For games (back-to-back etc.)")

