import streamlit as st
import pandas as pd
import math

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
    model_prob = min(0.85, max(0.50, 0.5 + norm_cdf(posterior / 11) * 0.35))
    edge = round(model_prob - market_p, 3)

    if edge >= 0.02 and posterior >= 3:
        regular = f"-{round(posterior - 1.5, 1)}"
        safe = f"-{round(max(1, posterior - 3.5), 1)}" if posterior >= 6 else "ML"
    elif edge >= 0.02:
        regular = "ML"
        safe = "ML"
    else:
        regular = "Pass"
        safe = "Pass"

    return {"model_prob": round(model_prob, 3), "edge": edge, "regular": regular, "safe": safe, "detail": f"Margin {round(posterior,1)}"}

def run_prop(row):
    proj = float(row.get("projection", 0) or 0)
    line = float(row.get("line", 0) or 0)
    market_p = float(row.get("market_prob", 0.5) or 0.5)
    std = float(row.get("std_dev", 0) or max(proj * 0.22, 1))
    hit_rate = float(row.get("season_hit_rate", 0.5) or 0.5)
    opp_adj = float(row.get("opponent_adj", 0) or 0)

    adj = proj + opp_adj
    diff = adj - line
    model_prob = min(0.82, max(0.50, 0.65 * norm_cdf(diff / std) + 0.35 * hit_rate))
    edge = round(model_prob - market_p, 3)
    direction = "Over" if diff >= 0 else "Under"

    if edge >= 0.025:
        regular = f"{direction} {line}"
        step = 10 if line >= 100 else 5 if line >= 30 else 2 if line >= 10 else 1
        safe_line = round(line - step if direction == "Over" else line + step, 1)
        safe = f"{direction} {safe_line}"
    else:
        regular = "Pass"
        safe = "Pass"

    return {"model_prob": round(model_prob, 3), "edge": edge, "regular": regular, "safe": safe, "detail": row.get("prop_type", "")}

st.set_page_config(page_title="Model Dashboard", layout="wide")
st.title("Personal Sports Model Dashboard")

uploaded = st.file_uploader("Upload CSV (games or props)", type="csv")
if uploaded:
    df = pd.read_csv(uploaded)
    st.dataframe(df, use_container_width=True)

    if st.button("Run Model", type="primary"):
        results = []
        for _, row in df.iterrows():
            if "projection" in df.columns and pd.notna(row.get("projection")):
                c = run_prop(row)
                results.append({
                    "type": "Prop",
                    "player": row.get("player", ""),
                    "matchup": row.get("matchup", ""),
                    "detail": c["detail"],
                    "model_prob": c["model_prob"],
                    "edge": c["edge"],
                    "regular": c["regular"],
                    "safe": c["safe"]
                })
            elif "prior_net_rating" in df.columns:
                c = run_game(row)
                results.append({
                    "type": "Game",
                    "player": "",
                    "matchup": row.get("matchup", ""),
                    "detail": c["detail"],
                    "model_prob": c["model_prob"],
                    "edge": c["edge"],
                    "regular": c["regular"],
                    "safe": c["safe"]
                })

        if results:
            out = pd.DataFrame(results)
            st.subheader("All Results")
            st.dataframe(out, use_container_width=True)
            rec = out[out["edge"] >= 0.02].sort_values("edge", ascending=False)
            st.subheader("Recommended")
            if len(rec):
                st.dataframe(rec, use_container_width=True)
            else:
                st.info("No plays cleared 2% edge.")
        else:
            st.warning("No valid game or prop rows found. Check column names.")

st.sidebar.markdown("**Games need:** prior_net_rating, recent_form, home_court, market_prob")
st.sidebar.markdown("**Props need:** projection, line, market_prob")
st.sidebar.caption("Safe lines use a simple fixed step. Match to Kalshi yourself.")
