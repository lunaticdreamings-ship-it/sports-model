import streamlit as st
import pandas as pd
import math

def norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))

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
    model_prob = min(0.82, max(0.50, 0.65 * norm_cdf(z) + 0.35 * hit_rate))
    edge = round(model_prob - market_p, 3)
    direction = "Over" if diff >= 0 else "Under"

    if edge >= 0.025:
        regular = f"{direction} {line}"
        # Simple one-step safe
        if line >= 100:
            step = 10
        elif line >= 30:
            step = 5
        elif line >= 10:
            step = 2
        else:
            step = 1
        safe_line = round(line - step, 1) if direction == "Over" else round(line + step, 1)
        safe = f"{direction} {safe_line}"
    else:
        regular = "Pass"
        safe = "Pass"

    return {
        "model_prob": round(model_prob, 3),
        "edge": edge,
        "regular": regular,
        "safe": safe
    }

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
                    "safe": c["safe"]
                })
        out = pd.DataFrame(rows)
        st.subheader("Results")
        st.dataframe(out, use_container_width=True)
        rec = out[out["edge"] >= 0.025].sort_values("edge", ascending=False)
        if len(rec):
            st.subheader("Recommended")
            st.dataframe(rec, use_container_width=True)
        else:
            st.info("No plays with edge ≥ 2.5%.")

st.sidebar.markdown("Safe line is one fixed step down. Match it to the closest real Kalshi market yourself.")
