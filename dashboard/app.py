import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import streamlit as st

st.set_page_config(page_title="Market Intelligence", layout="wide")

from dashboard.helpers import q, index_names, index_symbol, latest_date, data_banner

st.title("Market Intelligence (end-of-day)")
st.caption("What moved the index, how broad the move was, which stocks are strong, "
           "and which crossed key levels with volume.")
data_banner()
last = latest_date()

# ---------- index cards + plain-English summary ----------
st.subheader(f"Market snapshot: {last}")
names = index_names()
cols = st.columns(len(names))
summary = []
for col, name in zip(cols, names):
    sym = index_symbol(name)
    r = q("SELECT close, pct_change FROM gold_returns WHERE symbol=? AND date=?", (sym, last))
    t = q("SELECT trend FROM gold_trend WHERE symbol=? AND date=?", (sym, last))
    b = q("SELECT advances, declines FROM gold_breadth WHERE index_name=? AND date=?", (name, last))
    if len(r):
        chg = r["pct_change"][0]
        col.metric(name, f"{r['close'][0]:,.2f}", f"{chg:.2f}%")
        trend = t["trend"][0] if len(t) else "n/a"
        col.write(f"Trend: **{trend}**")
        if len(b):
            adv, dec = int(b["advances"][0]), int(b["declines"][0])
            col.write(f"Advances: {adv} | Declines: {dec}")
            word = "rose" if chg >= 0 else "fell"
            summary.append(f"**{name}** {word} {abs(chg):.2f}%, with {adv} stocks up and "
                           f"{dec} down. Trend is {trend}.")
if summary:
    st.info("  \n".join(summary))

# ---------- confirmed level events ----------
ev = q("SELECT event, COUNT(*) AS n FROM gold_levels WHERE date=? GROUP BY event", (last,))
ev = dict(zip(ev["event"], ev["n"]))
e1, e2, e3, e4 = st.columns(4)
e1.metric("Confirmed breakouts", ev.get("breakout confirmed", 0))
e2.metric("Confirmed breakdowns", ev.get("breakdown confirmed", 0))
e3.metric("Failed breakouts", ev.get("failed breakout", 0))
e4.metric("Low-volume crosses",
          ev.get("breakout on low volume", 0) + ev.get("breakdown on low volume", 0))
st.caption("Confirmed = price crossed the previous day's high/low with volume above "
           "the 20-day average. Low-volume crosses are not treated as signals.")

# ---------- gainers / losers ----------
mv = q("""SELECT i.name AS Stock, r.close AS Close, r.pct_change AS "Change %"
          FROM gold_returns r JOIN instruments i ON i.symbol = r.symbol
          WHERE i.kind='stock' AND r.date=? AND r.pct_change IS NOT NULL
          ORDER BY r.pct_change DESC""", (last,))
g, l = st.columns(2)
with g:
    st.subheader("Top 5 gainers")
    st.dataframe(mv.head(5).round(2), hide_index=True, use_container_width=True)
with l:
    st.subheader("Top 5 losers")
    st.dataframe(mv.tail(5).iloc[::-1].round(2), hide_index=True, use_container_width=True)

# ---------- contributors / draggers (first index) ----------
idx = names[0]
st.subheader(f"What moved {idx} (weight x stock move)")
c = q("""SELECT i.name AS Stock, c.weight*100 AS "Weight %", c.pct_change AS "Move %",
                c.contribution AS Contribution
         FROM gold_contribution c JOIN instruments i ON i.symbol = c.symbol
         WHERE c.index_name=? AND c.date=? ORDER BY c.contribution DESC""", (idx, last))
a, d = st.columns(2)
with a:
    st.markdown("**Top contributors**")
    st.dataframe(c.head(5).round(3), hide_index=True, use_container_width=True)
with d:
    st.markdown("**Top draggers**")
    st.dataframe(c.tail(5).iloc[::-1].round(3), hide_index=True, use_container_width=True)

# ---------- navigation ----------
st.subheader("Explore")
n1, n2, n3, n4, n5 = st.columns(5)
n1.page_link("pages/1_Market_Overview.py", label="Market Overview")
n2.page_link("pages/2_Index_Drivers.py", label="Index Drivers")
n3.page_link("pages/3_Stock_Scanner.py", label="Stock Scanner")
n4.page_link("pages/4_Stock_Detail.py", label="Stock Detail")
n5.page_link("pages/5_Backtest.py", label="Backtest")

st.caption("Analysis only, not investment advice. Data: Yahoo Finance (end of day). "
           "Index weights are approximate (market-cap based), not official.")