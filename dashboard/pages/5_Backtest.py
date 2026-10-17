import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import pandas as pd
import plotly.express as px
import streamlit as st
from src.db import load_config
from src.backtest.engine import run_backtest
from src.backtest.metrics import summarize

st.title("Backtest")
st.write("**Rule tested:** close breaks above the previous day high with volume "
         "above X times the 20-day average. Enter at the **next day's open**, "
         "exit after N days or at the stop-loss.")

cfg_all = load_config()
cfg = cfg_all.get("backtest", {})

c1, c2, c3, c4 = st.columns(4)
hold = c1.slider("Hold days", 1, 20, int(cfg.get("hold_days", 5)))
stop = c2.slider("Stop loss % (0 = none)", 0.0, 10.0,
                 float(cfg.get("stop_loss_pct", 3.0)), 0.5)
vol = c3.slider("Volume multiple", 1.0, 3.0,
                float(cfg_all["thresholds"]["breakout_volume_multiple"]), 0.1)
buf = c4.slider("Min breakout above PDH %", 0.0, 1.0,
                float(cfg.get("breakout_buffer_pct", 0.0)), 0.05)
cost = st.slider("Cost per side % (brokerage, tax, slippage)", 0.0, 0.5,
                 float(cfg.get("cost_pct_per_side", 0.1)), 0.05)


@st.cache_data(ttl=600)
def cached(hold, stop, cost, vol, buf):
    return run_backtest(hold, stop, cost, vol, buf)


with st.spinner("Running backtest..."):
    t, b = cached(hold, stop, cost, vol, buf)

if len(t) == 0:
    st.warning("No trades with these settings.")
    st.stop()

s, bs = summarize(t), summarize(b)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Trades", s["trades"])
m2.metric("Win rate", f"{s['win_rate_pct']}%",
          f"{s['win_rate_pct'] - bs['win_rate_pct']:+.1f} vs baseline")
m3.metric("Avg return per trade", f"{s['avg_return_pct']}%",
          f"{s['avg_return_pct'] - bs['avg_return_pct']:+.3f} vs baseline")
m4.metric("Max drawdown", f"{s['max_drawdown_pts']} pts")

st.subheader("Rule vs baseline")
st.dataframe(pd.DataFrame({"Breakout rule": s,
                           "Baseline (any stock, any day)": bs}).astype(str),
             use_container_width=True)
st.caption("If the rule's average return is not clearly above the baseline, "
           "the rule has no real edge on this data.")

st.subheader("Cumulative return of trades (sum of % returns)")
e = t.sort_values("exit_date").copy()
e["cum_return_pct"] = e["ret_pct"].cumsum()
st.plotly_chart(px.line(e, x="exit_date", y="cum_return_pct"),
                use_container_width=True)

st.subheader("By year")
t["year"] = t["entry_date"].astype(str).str[:4]
yr = t.groupby("year")["ret_pct"].agg(
    trades="count", avg_return="mean",
    win_rate=lambda x: (x > 0).mean() * 100).round(2)
st.dataframe(yr, use_container_width=True)

st.subheader("How trades ended")
st.write(t["exit_reason"].value_counts().rename_axis("exit").to_frame("trades"))

st.subheader("All trades")
st.dataframe(t.drop(columns=["year"]).sort_values("entry_date", ascending=False).round(2),
             hide_index=True, use_container_width=True)

st.caption(
    "Limits: uses today's index stock list (stocks that dropped out are missing, "
    "which flatters results); about 4-5 years of data; costs are estimates; "
    "dividends ignored; past results do not predict future results. "
    "This is analysis, not investment advice.")