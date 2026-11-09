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

def norm_cdf(x, mu=0, sigma=11):
    return 0.5 * (1 + math.erf((x - mu) / (sigma * math.sqrt(2))))

def run_game(row):
    prior = float(row.get("prior_net_rating", 0) or 0)
    recent = float(row.get("recent_form", 0) or 0)
    home = float(row.get("home_court", 0) or 0)
    injury = float(row.get("injury_adj", 0) or 0)
    market_p = float(row.get("market_prob", 0.5) or 0.5)

    posterior = (0.6 * prior) + (0.4 * recent) + home + injury
    cover_prob = norm_cdf(posterior, mu=0, sigma=11)
    model_prob = min(0.88, max(0.50, cover_prob))
    edge = round(model_prob - market_p, 3)

    # Suggested spreads
    if posterior >= 8:
        regular_spread = f"-{round(posterior - 1.5, 1)}"
        safe_spread = f"-{round(posterior - 3.5, 1)}"
    elif posterior >= 4:
        regular_spread = f"-{round(posterior - 1, 1)}"
        safe_spread = f"-{round(max(1, posterior - 2.5), 1)}"
    else:
        regular_spread = "ML or small spread"
        safe_spread = "ML"

    return {
        "type": "Game",
        "posterior_margin": round(posterior, 1),
        "model_prob": round(model_prob, 3),
        "edge": edge,
        "regular": regular_spread if edge >= 0.02 else "Pass",
        "safe": safe_spread if edge >= 0.02 else "Pass"
    }

def run_prop(row):
    projection = float(row.get("projection", 0) or 0)
    line = float(row.get("line", 0) or 0)
    market_p = float(row.get("market_prob", 0.5) or 0.5)

    diff = projection - line
    # Simple probability from difference
    model_prob = min(0.85, max(0.50, 0.5 + (diff * 0.04)))
    edge = round(model_prob - market_p, 3)

    if edge >= 0.03:
        regular = f"Over {line}" if diff > 0 else f"Under {line}"
        safe_line = line - 2 if diff > 0 else line + 2
        safe = f"Over {safe_line}" if diff > 0 else f"Under {safe_line}"
    else:
        regular = "Pass"
        safe = "Pass"

    return {
        "type": "Prop",
        "projection": projection,
        "line": line,
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
st.caption("Game columns: sport, matchup, prior_net_rating, recent_form, home_court, injury_adj, market_prob")
st.caption("Prop columns: sport, player, prop_type, projection, line, market_prob, matchup")

uploaded = st.file_uploader("Upload CSV", type="csv")
if uploaded:
    df = pd.read_csv(uploaded)
    st.subheader("Input")
    st.dataframe(df, use_container_width=True)

    if st.button("Run Model", type="primary"):
        results = []
        for _, row in df.iterrows():
            if "projection" in df.columns and pd.notna(row.get("projection")):
                calc = run_prop(row)
                results.append({
                    "sport": row.get("sport", ""),
                    "matchup": row.get("matchup", ""),
                    "player": row.get("player", ""),
                    "type": "Prop",
                    "detail": f"{row.get('prop_type', '')} {row.get('line', '')}",
                    "model_prob": calc["model_prob"],
                    "edge": calc["edge"],
                    "regular": calc["regular"],
                    "safe": calc["safe"]
                })
            else:
                calc = run_game(row)
                results.append({
                    "sport": row.get("sport", ""),
                    "matchup": row.get("matchup", ""),
                    "player": "",
                    "type": "Game",
                    "detail": f"Margin {calc['posterior_margin']}",
                    "model_prob": calc["model_prob"],
                    "edge": calc["edge"],
                    "regular": calc["regular"],
                    "safe": calc["safe"]
                })

        out = pd.DataFrame(results)
        plays = out[out["edge"] >= 0.02].sort_values("edge", ascending=False)

        st.subheader("All Results")
        st.dataframe(out, use_container_width=True)

        st.subheader("Recommended (Edge ≥ 2%)")
        if len(plays) > 0:
            st.dataframe(plays, use_container_width=True)
            try:
                slip = {"date": date.today().isoformat(), "plays": plays.to_dict("records")}
                if "slips" not in st.session_state.log:
                    st.session_state.log["slips"] = []
                st.session_state.log["slips"].append(slip)
                save_log(st.session_state.log)
            except:
                pass
        else:
            st.info("No plays with edge ≥ 2%.")

st.sidebar.markdown("### Game CSV Example")
st.sidebar.code("sport,matchup,prior_net_rating,recent_form,home_court,injury_adj,market_prob")
st.sidebar.markdown("### Prop CSV Example")
st.sidebar.code("sport,player,prop_type,projection,line,market_prob,matchup")

