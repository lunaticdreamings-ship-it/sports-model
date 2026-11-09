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

def run_model(row):
    """Bayesian-style update and cover probability."""
    prior = float(row.get("prior_net_rating", 0))
    recent = float(row.get("recent_form", 0))
    home = float(row.get("home_court", 0))
    injury = float(row.get("injury_adj", 0))
    market_p = float(row.get("market_prob", 0.5))

    # Weighted posterior margin
    posterior = (0.6 * prior) + (0.4 * recent) + home + injury

    # Cover probability vs a -market line approximation
    # Higher posterior = higher cover chance
    cover_prob = norm_cdf(posterior, mu=0, sigma=11)
    model_prob = min(0.88, max(0.52, cover_prob))

    edge = round(model_prob - market_p, 3)

    if edge >= 0.04:
        regular = f"Lean (edge {edge})"
        safe = "Safer number"
    elif edge >= 0.02:
        regular = "Slight lean"
        safe = "Pass or reduce"
    else:
        regular = "Pass"
        safe = "Pass"

    return {
        "posterior_margin": round(posterior, 1),
        "model_prob": round(model_prob, 3),
        "edge": edge,
        "regular_lean": regular,
        "safe_lean": safe
    }

if "log" not in st.session_state:
    st.session_state.log = load_log()

st.set_page_config(page_title="Model Dashboard", layout="wide")
st.title("Personal Sports Model Dashboard")

st.header("Upload Model Input")
st.caption("Upload a CSV with columns: sport, matchup, prior_net_rating, recent_form, home_court, injury_adj, market_prob")

uploaded = st.file_uploader("Upload CSV", type="csv")
if uploaded:
    df = pd.read_csv(uploaded)
    st.subheader("Input Data")
    st.dataframe(df, use_container_width=True)

    if st.button("Run Model", type="primary"):
        results = []
        for _, row in df.iterrows():
            calc = run_model(row)
            results.append({
                "sport": row.get("sport", ""),
                "matchup": row.get("matchup", ""),
                "posterior_margin": calc["posterior_margin"],
                "model_prob": calc["model_prob"],
                "market_prob": row.get("market_prob", ""),
                "edge": calc["edge"],
                "regular_lean": calc["regular_lean"],
                "safe_lean": calc["safe_lean"],
                "notes": row.get("notes", "")
            })

        out = pd.DataFrame(results)
        # Filter to positive edge
        plays = out[out["edge"] >= 0.02].sort_values("edge", ascending=False)

        st.subheader("Model Output")
        st.dataframe(out, use_container_width=True)

        st.subheader("Recommended Plays (Edge ≥ 2%)")
        if len(plays) > 0:
            st.dataframe(plays, use_container_width=True)
            slip = {
                "date": date.today().isoformat(),
                "plays": plays.to_dict("records"),
                "generated_at": datetime.now().isoformat()
            }
            st.session_state.log["slips"].append(slip)
            save_log(st.session_state.log)
        else:
            st.info("No plays cleared the 2% edge threshold.")

st.sidebar.markdown("### Template Columns")
st.sidebar.code("""sport,matchup,prior_net_rating,
recent_form,home_court,injury_adj,
market_prob,notes""")
st.sidebar.caption("Fill these in and upload.")

