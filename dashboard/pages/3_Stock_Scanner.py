import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import pandas as pd
import streamlit as st
from dashboard.helpers import q, index_names, latest_date, data_banner

BULL_OK = {"breakout confirmed", "retest held (above PDH)"}
BEAR_OK = {"breakdown confirmed", "retest held (below PDL)"}
MIN_SCORE = 4

st.title("Stock Scanner")
data_banner()
last = latest_date()
st.caption(f"Candidates for {last}. Analysis flags with evidence, not buy/sell advice. "
           "Scores are only comparable within the same maximum (x/5 or x/6).")

# ---- NEW: setups vs watchlist ----
c = q("""SELECT c.symbol, i.name, c.bull_score, c.bear_score, c.max_score,
                c.bull_components, c.bull_against, c.bear_components,
                c.bear_against, l.event,
                r.volume * 1.0 / r.avg_vol_20 AS vol_ratio
         FROM gold_candidates c
         JOIN instruments i ON i.symbol = c.symbol
         LEFT JOIN gold_levels l ON l.symbol = c.symbol AND l.date = c.date
         LEFT JOIN gold_returns r ON r.symbol = c.symbol AND r.date = c.date
         WHERE c.date = ? AND (c.bull_score >= ? OR c.bear_score >= ?)""",
      (last, MIN_SCORE, MIN_SCORE))

setups, watch = [], []
for r in c.itertuples():
    bull = r.bull_score >= r.bear_score
    side = "BULLISH" if bull else "BEARISH"
    score = r.bull_score if bull else r.bear_score
    ev = r.event if r.event else "none"
    against = r.bull_against if bull else r.bear_against
    parts = [] if (not against or against == "none") else [str(against)]
    if pd.notna(r.vol_ratio) and r.vol_ratio < 1.0:
        parts.append(f"low volume {r.vol_ratio:.1f}x")
    item = dict(side=side, name=r.name, score=score, max=r.max_score, event=ev,
                evidence=r.bull_components if bull else r.bear_components,
                against="; ".join(parts) if parts else "none")
    ok = ev in (BULL_OK if bull else BEAR_OK)
    (setups if ok else watch).append(item)


def show(items):
    items.sort(key=lambda x: (x["side"], -x["score"] / x["max"]))
    for x in items:
        title = (f"{x['side']} | {x['name']} | score {x['score']:.0f}/{x['max']} "
                 f"({x['score'] / x['max']:.0%}) | {x['event']}")
        with st.expander(title):
            st.write("**Evidence:** " + str(x["evidence"]))
            st.write("**Against:** " + x["against"])


st.subheader(f"Setups ({len(setups)}): confirmed price-level event")
if setups:
    show(setups)
else:
    st.info("No confirmed setups today.")

st.subheader(f"Watchlist ({len(watch)}): good score, no confirmed event")
if watch:
    show(watch)
else:
    st.info("Watchlist is empty.")

# ---- existing: simple breakout/breakdown list (kept) ----
st.subheader("Simple breakout / breakdown list")
sig = q("""SELECT s.symbol, i.name, s.signal, s.reason
           FROM gold_signals s JOIN instruments i ON i.symbol=s.symbol
           WHERE s.date=?""", (last,))
kind = st.multiselect("Signal type", ["BREAKOUT", "BREAKDOWN"],
                      default=["BREAKOUT", "BREAKDOWN"])
st.dataframe(
    sig[sig["signal"].isin(kind)],
    use_container_width=True,
    hide_index=True,
    column_config={"reason": st.column_config.TextColumn("reason", width="large")},
)

# ---- relative strength (FIXED: now shows rs, not sig) ----
st.subheader("Relative strength (20 days)")
idx = st.selectbox("Compare against", index_names(), index=1)
rs = q("""SELECT i.name, r.stock_ret AS stock_20d, r.index_ret AS index_20d,
                 r.rs AS rs_vs_index, r.rs_vs_nifty50
          FROM gold_relative_strength r JOIN instruments i ON i.symbol=r.symbol
          WHERE r.index_name=? AND r.date=? ORDER BY r.rs DESC""", (idx, last))
st.dataframe(rs.round(2), use_container_width=True, hide_index=True)