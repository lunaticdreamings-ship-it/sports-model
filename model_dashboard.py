import streamlit as st
import pandas as pd
import math
import json
import os
from datetime import date

def norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))

def pillars(row, is_prop=False):
    flags = []
    mult = 1.0
    notes = []

    # 1. Injury
    inj = str(row.get("key_injury", "")).lower().strip()
    if inj in ["out", "yes"]:
        mult *= 0.80
        flags.append("OUT")
    elif inj in ["questionable", "q", "doubtful"]:
        mult *= 0.92
        flags.append("Q")

    # 2. Rest
    rest_days = float(row.get("days_rest", 2) or 2)
    if rest_days <= 1:
        mult *= 0.88
        flags.append("B2B")

    # 3. Form disagreement (games)
    if not is_prop:
        prior = float(row.get("prior_net_rating", 0) or 0)
        recent = float(row.get("recent_form", 0) or 0)
        if abs(prior - recent) >= 7:
            mult *= 0.90
            flags.append("FormSplit")

    # 4. Variance flag (props)
    if is_prop:
        std = float(row.get("std_dev", 0) or 0)
        line = float(row.get("line", 0) or 1)
        if std > line * 0.35:
            mult *= 0.93
            flags.append("HighVar")

    # 5. Market edge already handled later
    # 6. Blowout risk (simple)
    if not is_prop:
        posterior_est = float(row.get("prior_net_rating", 0) or 0) + float(row.get("home_court", 0) or 0)
        if posterior_est >= 12:
            flags.append("BlowoutRisk")
            notes.append("Starters may rest")

    # 7. Opponent strength note
    opp = float(row.get("opponent_adj", 0) or 0)
    if is_prop and opp <= -2:
        mult *= 0.94
        flags.append("ToughMatchup")

    return mult, flags, notes

def run_game(row):
    prior = float(row.get("prior_net_rating", 0) or 0)
    recent = float(row.get("recent_form", 0) or 0)
    home = float(row.get("home_court", 0) or 0)
    inj_adj = float(row.get("injury_adj", 0) or 0)
    rest_adj = float(row.get("rest_adj", 0) or 0)
    mkt = float(row.get("market_prob", 0.5) or 0.5)

    mult, flags, notes = pillars(row, False)
    posterior = (0.50*prior + 0.30*recent + home + inj_adj + rest_adj) * mult
    prob = min(0.87, max(0.47, 0.50 + norm_cdf(posterior/11)*0.37))
    edge = round(prob - mkt, 3)

    fav = str(row.get("favorite") or str(row.get("matchup","")).split(" vs ")[0]).strip()
    if "OUT" in flags or edge < 0.015:
        reg = safe = "Pass"
    elif posterior >= 4:
        reg = f"{fav} -{round(posterior-1.5,1)}"
        safe = f"{fav} -{round(max(1,posterior-3.5),1)}" if posterior >= 6.5 else f"{fav} ML"
    else:
        reg = safe = f"{fav} ML"

    return {"prob": round(prob,3), "edge": edge, "regular": reg, "safe": safe,
            "detail": f"Margin {round(posterior,1)}", "flags": " ".join(flags) or "—", "notes": "; ".join(notes)}

def run_prop(row):
    proj = float(row.get("projection", 0) or 0)
    line = float(row.get("line", 0) or 0)
    mkt = float(row.get("market_prob", 0.5) or 0.5)
    std = float(row.get("std_dev", 0) or max(proj*0.22,1))
    hit = float(row.get("season_hit_rate", 0.5) or 0.5)
    opp = float(row.get("opponent_adj", 0) or 0)

    mult, flags, notes = pillars(row, True)
    adj = (proj + opp) * mult
    diff = adj - line
    prob = min(0.84, max(0.47, 0.60*norm_cdf(diff/std) + 0.40*hit))
    edge = round(prob - mkt, 3)
    direction = "Over" if diff >= 0 else "Under"

    if "OUT" in flags or edge < 0.02:
        reg = safe = "Pass"
    else:
        reg = f"{direction} {line}"
        step = 10 if line >= 100 else 5 if line >= 20 else 2
        safe_line = round(line - step if direction=="Over" else line + step, 1)
        safe = f"{direction} {safe_line}"

    return {"prob": round(prob,3), "edge": edge, "regular": reg, "safe": safe,
            "detail": f"{row.get('prop_type','')} adj {round(adj,1)}", "flags": " ".join(flags) or "—", "notes": "; ".join(notes)}

st.set_page_config(page_title="Model", layout="wide")
st.title("Sports Model Dashboard")
st.caption("Pillars: Injury · Rest · Form Split · Variance · Blowout Risk · Matchup")

gfile = st.file_uploader("Games CSV", type="csv")
pfile = st.file_uploader("Props CSV", type="csv")

if st.button("Run", type="primary"):
    plays = []
    if gfile:
        for _, r in pd.read_csv(gfile).iterrows():
            if pd.notna(r.get("prior_net_rating")):
                res = run_game(r)
                if res["regular"] != "Pass":
                    plays.append({"type":"Game", "name": r.get("matchup"), **res})
    if pfile:
        for _, r in pd.read_csv(pfile).iterrows():
            if pd.notna(r.get("projection")):
                res = run_prop(r)
                if res["regular"] != "Pass":
                    plays.append({"type":"Prop", "name": f"{r.get('player')} {r.get('prop_type')}", **res})

    if plays:
        df = pd.DataFrame(plays).sort_values("edge", ascending=False)
        st.dataframe(df, use_container_width=True)
        st.subheader("Slip")
        for _, p in df.head(5).iterrows():
            st.write(f"**{p['regular']}** · {p['name']} · {p['prob']*100:.0f}% · {p['flags']}")
        st.subheader("Safe")
        for _, p in df.head(5).iterrows():
            st.write(f"**{p['safe']}** · {p['name']}")
    else:
        st.warning("No plays cleared pillars + edge. Check key_injury, projections, or market_prob.")

st.sidebar.markdown("""
**Pillar Columns**
- key_injury: out / questionable / blank
- days_rest: 0-1 = back-to-back
- opponent_adj: negative = tough matchup
- std_dev: high = variance flag
""")
