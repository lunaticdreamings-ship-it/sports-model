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

def find_kalshi_player_lines(player_name):
    """Return all numeric lines from markets that mention the player."""
    try:
        url = "https://api.elections.kalshi.com/trade-api/v2/markets"
        r = requests.get(url, params={"limit": 200, "status": "open"}, timeout=10)
        if r.status_code != 200:
            return []
        markets = r.json().get("markets", [])
        last = str(player_name).lower().strip() if player_name else ""
        if not last or len(last) < 4:
            return []
        lines = []
        for m in markets:
            title = ((m.get("title") or "") + " " + (m.get("subtitle") or "")).lower()
            # Match full name or significant parts
            if last in title or all(part in title for part in last.split() if len(part) > 2):
                nums = re.findall(r"(\d+\.?\d*)", title)
                for n in nums:
                    val = float(n)
                    if val >= 1:
                        lines.append(val)
        return sorted(set(lines))
    except:
        return []

def run_prop(row):
    proj = float(row.get("projection", 0) or 0)
    line = float(row.get("line", 0) or 0)
    market_p = float(row.get("market_prob", 0.5) or 0.5)
    std = float(row.get("std_dev", 0) or max(proj * 0.22, 1))
    hit_rate = float(row.get("season_hit_rate", 0.5) or 0.5)
    opp_adj = float(row.get("opponent_adj", 0) or 0)

    adj_proj = proj + opp_adj
    diff = adj_proj - line
    z = diff / std if std else 0
    raw = norm_cdf(z)
    model_prob = min(0.82, max(0.50, 0.65 * raw + 0.35 * hit_rate))
    edge = round(model_prob - market_p, 3)
    direction = "Over" if diff >= 0 else "Under"

    kalshi_lines = find_kalshi_player_lines(row.get("player", ""))

    if edge >= 0.025:
        regular = f"{direction} {line}"
        # Next real Kalshi line in the safe direction
        if kalshi_lines and direction == "Over":
            lower = [l for l in kalshi_lines if l < line]
            safe_line = max(lower) if lower else line
        elif kalshi_lines and direction == "Under":
            higher = [l for l in kalshi_lines if l > line]
            safe_line = min(higher) if higher else line
        else:
            safe_line = line
        safe = f"{direction} {safe_line}" if safe_line != line else regular
    else:
        regular = "Pass"
        safe = "Pass"
        safe_line = None

    return {
        "adj_projection": round(adj_proj, 1),
        "model_prob": round(model_prob, 3),
        "edge": edge,
        "regular": regular,
        "safe": safe,
        "kalshi_lines": kalshi_lines
    }

if "log" not in st.session_state:
    st.session_state.log = load_log()

st.set_page_config(page_title="Model Dashboard", layout="wide")
st.title("Personal Sports Model Dashboard")

uploaded = st.file_uploader("Upload Prop CSV", type="csv")
if uploaded:
    df = pd.read_csv(uploaded)
    st.dataframe(df, use_container_width=True)
    if st.button("Run Model", type="primary"):
        rows = []
        for _, row in df.iterrows():
            if pd.notna(row.get("projection")):
                c = run_prop(row)
                rows.append({
                    "player": row.get("player"),
                    "prop": row.get("prop_type"),
                    "matchup": row.get("matchup"),
                    "model_prob": c["model_prob"],
                    "edge": c["edge"],
                    "regular": c["regular"],
                    "safe": c["safe"],
                    "kalshi_lines_found": str(c["kalshi_lines"])
                })
        out = pd.DataFrame(rows)
        st.subheader("Results")
        st.dataframe(out, use_container_width=True)
        rec = out[out["edge"] >= 0.025]
        if len(rec):
            st.subheader("Recommended")
            st.dataframe(rec.sort_values("edge", ascending=False), use_container_width=True)

st.sidebar.caption("Safe line = next real Kalshi line below (for Overs) or above (for Unders) the model's line.")
