import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import plotly.express as px
import streamlit as st
from dashboard.helpers import q, index_names, index_symbol, latest_date, data_banner  # NEW: data_banner

st.title("Market Overview")
data_banner()  # NEW
last = latest_date()

cols = st.columns(len(index_names()))
for col, name in zip(cols, index_names()):
    sym = index_symbol(name)
    r = q("SELECT close, pct_change FROM gold_returns WHERE symbol=? AND date=?",
          (sym, last))
    t = q("SELECT trend FROM gold_trend WHERE symbol=? AND date=?", (sym, last))
    b = q("SELECT advances, declines FROM gold_breadth "
          "WHERE index_name=? AND date=?", (name, last))
    if len(r):
        col.metric(name, f"{r['close'][0]:,.2f}", f"{r['pct_change'][0]:.2f}%")
        col.write(f"Trend: **{t['trend'][0]}**")
        if len(b):
            col.write(f"Advances: {b['advances'][0]} | Declines: {b['declines'][0]}")

# ---- NEW: heatmap ----
st.subheader("Heatmap: today's move by stock (box size = index weight)")
hm_idx = st.selectbox("Index", index_names(), index=0, key="hm_idx")
hm = q("""SELECT i.name, c.weight*100 AS weight_pct, c.pct_change
          FROM gold_contribution c JOIN instruments i ON i.symbol=c.symbol
          WHERE c.index_name=? AND c.date=?""", (hm_idx, last))
hm = hm[hm["weight_pct"] > 0]
if len(hm):
    fig_hm = px.treemap(hm, path=["name"], values="weight_pct", color="pct_change",
                        color_continuous_scale="RdYlGn", color_continuous_midpoint=0,
                        range_color=[-3, 3])
    fig_hm.update_traces(texttemplate="%{label}<br>%{color:.2f}%")
    fig_hm.update_layout(height=500, margin=dict(t=10, l=0, r=0, b=0))
    st.plotly_chart(fig_hm, use_container_width=True)
else:
    st.info("No heatmap data for this date.")

# ---- existing performance chart ----
st.subheader("Index performance (rebased to 100)")
sel = st.selectbox("Period", ["3 months", "6 months", "1 year", "All"], index=1)
days = {"3 months": 63, "6 months": 126, "1 year": 252, "All": 100000}[sel]
syms = [index_symbol(n) for n in index_names()]
ph = ",".join("?" * len(syms))
df = q(f"SELECT symbol, date, close FROM gold_returns WHERE symbol IN ({ph})",
       tuple(syms))
df = df.sort_values("date")
df = df.groupby("symbol").tail(days).copy()
df["rebased"] = df.groupby("symbol")["close"].transform(lambda s: s / s.iloc[0] * 100)
names = {index_symbol(n): n for n in index_names()}
df["index"] = df["symbol"].map(names)
st.plotly_chart(
    px.line(df, x="date", y="rebased", color="index",
            color_discrete_map={"NIFTY50": "#f59e0b", "NIFTYPHARMA": "#22c55e"}),
    use_container_width=True)