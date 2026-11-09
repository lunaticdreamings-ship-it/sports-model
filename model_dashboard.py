import streamlit as st
import pandas as pd
import json
import os
import math
import re
import requests
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

def find_kalshi_alternates(player_name, prop_type):
    try:
        url = "https://api.elections.kalshi.com/trade-api/v2/markets"
        params = {"limit": 100, "status": "open"}
        r = requests.get(url, params=params, timeout=8)
        if r.status_code != 200:
            return []
        markets = r.json().get("markets", [])
        matches = []
        player_lower = str(player_name).lower().split()[-1] if player_name else ""
        prop_lower = str(prop_type).lower()
        for m in markets:
            title = (m.get("title", "") + " " + m.get("subtitle", "")).lower()
            if player_lower and player_lower in title:
                nums = re.findall(r"(\d+\.?\d*)", title)
                if nums:
                    matches.append({"line": float(nums[0]), "title": m.get("title", "")[:70]})
        return matches[:6]
    except:
        return []

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
        regular = f"-{round(posterior - 2, 1)}"
        safe = f"-{round(max(1, posterior - 4), 1)}"
    elif posterior >= 3:
        regular = f"-{round(posterior - 1.5, 1)}"
        safe = "ML"
    else:
        regular = "ML"
        safe = "ML"
    return {"posterior": round(posterior, 1), "model_prob": round(model_prob, 3), "edge": edge,
            "regular": regular if edge >= 0.02 else "Pass", "safe": safe if edge >= 0.02 else "Pass"}

def run_prop(row):
    proj = float(row.get("projection", 0) or 0)
    line = float(row.get("line", 0) or 0)
    market_p = float(row.get("market_prob", 0.5) or 0.5)
    std = float(row.get("std_dev", 0) or (proj * 0.25))
    hit_rate = float(row.get("season_hit_rate", 0.5) or 0.5)
    opp_adj = float(row.get("opponent_adj", 0) or 0)
    adj_proj = proj + opp_adj
    diff = adj_proj - line
    z = diff / std if std > 0 else 0
    raw_prob = norm_cdf(z)
    model_prob = min(0.84, max(0.48, (0.7 * raw_prob) + (0.3 * hit_rate)))
    edge = round(model_prob - market_p, 3)
    direction = "Over" if diff > 0 else "Under"

    alternates = find_kalshi_alternates(row.get("player", ""), row.get("prop_type", ""))
    available = sorted(set(a["line"] for a in alternates))

    if edge >= 0.03:
        regular = f"{direction} {line}"
        if available and diff > 0:
            safer = [l for l in available if l < line - 0.5]
            safe_line = max(safer) if safer else round(line - (10 if line > 50 else 2), 1)
        elif available and diff < 0:
            safer = [l for l in available if l > line + 0.5]
            safe_line = min(safer) if safer else round(line + 2, 1)
        else:
            safe_line = round(line - (15 if line > 100 else 8 if line > 40 else 3), 1)
        safe = f"{direction} {safe_line}"
    else:
        regular = "Pass"
        safe = "Pass"
        safe_line = None

    return {"adj_projection": round(adj_proj, 1), "model_prob": round(model_prob, 3), "edge": edge,
            "regular": regular, "safe": safe, "kalshi_lines": available[:4]}

if "log" not in st.session_state:
    st.session_state.log = load_log()

st.set_page_config(page_title="Model Dashboard", layout="wide")
st.title("Personal Sports Model Dashboard")

st.header("Upload Input CSV")
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
                    "safe": c["safe"],
                    "kalshi_available": str(c["kalshi_lines"])
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
                    "safe": c["safe"],
                    "kalshi_available": ""
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

st.sidebar.markdown("Safe lines now check Kalshi for real available alternates when possible.")
