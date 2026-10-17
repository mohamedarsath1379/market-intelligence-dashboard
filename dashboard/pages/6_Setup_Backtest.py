import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import pandas as pd
import plotly.express as px
import streamlit as st
from src.backtest.setup_backtest import run_setup_backtest, summarize

st.title("Setup Backtest")
st.write("**Rule tested:** the scanner's setups: score at or above the minimum "
         "plus a confirmed breakout/breakdown. The signal is known at the close; "
         "entry is the **next day's open**. Exit after N days or at the stop. "
         "Costs are charged on both sides. Compared against random stocks "
         "picked on the same dates.")

c1, c2, c3, c4 = st.columns(4)
hold = c1.slider("Hold days", 2, 7, 5)
stop = c2.slider("Stop loss % (0 = none)", 0.0, 8.0, 3.0, 0.5)
cost = c3.slider("Cost per side %", 0.0, 0.5, 0.1, 0.05)
min_score = c4.slider("Minimum score", 3, 5, 4)


@st.cache_data(ttl=600)
def cached(hold, stop, cost, min_score):
    return run_setup_backtest(hold, stop, cost, min_score)


with st.spinner("Running backtest and 1000 random baselines..."):
    t, base = cached(hold, stop, cost, min_score)

if len(t) == 0:
    st.warning("No trades with these settings.")
    st.stop()

st.subheader("Result by side")
for side in ["BULLISH", "BEARISH"]:
    ts = t[t["side"] == side]
    if len(ts) == 0:
        continue
    st.markdown(f"**{side}**")
    s = summarize(ts)
    m = st.columns(4)
    m[0].metric("Trades", s["trades"])
    m[1].metric("Win rate", f"{s['win_rate_%']}%")
    m[2].metric("Avg return/trade", f"{s['avg_return_%']}%")
    m[3].metric("Profit factor", s["profit_factor"])
    b = base.get(side)
    if b:
        msg = (f"Random stocks on the same dates: average {b['random_mean']:.3f}%, "
               f"90% range {b['p5']:.3f}% to {b['p95']:.3f}%. "
               f"Setup edge vs random: {b['edge']:+.3f}% per trade. "
               f"The setup beat {b['pct_random_beaten']:.0f}% of random runs.")
        if len(ts) < 30:
            st.warning(f"Only {len(ts)} trades, too few to conclude anything. " + msg)
        elif b["pct_random_beaten"] >= 95:
            st.success("Better than random on this data. " + msg)
        else:
            st.info("No clear edge over random on this data. " + msg)

st.subheader("By event type")
st.dataframe(t.groupby(["side", "event"])["ret_pct"].agg(
    trades="count", avg_return="mean",
    win_rate=lambda x: (x > 0).mean() * 100).round(2), use_container_width=True)

st.subheader("By Nifty 50 trend on signal day")
st.dataframe(t.groupby(["side", "nifty50_trend"])["ret_pct"].agg(
    trades="count", avg_return="mean",
    win_rate=lambda x: (x > 0).mean() * 100).round(2), use_container_width=True)

st.subheader("Cumulative return (sum of % returns)")
e = t.sort_values("exit_date").copy()
e["cum"] = e.groupby("side")["ret_pct"].cumsum()
st.plotly_chart(px.line(e, x="exit_date", y="cum", color="side"),
                use_container_width=True)

st.subheader("How trades ended")
st.write(t.groupby(["side", "exit_reason"]).size().rename("trades").to_frame())

st.subheader("All trades")
st.dataframe(t.sort_values("signal_date", ascending=False).round(2),
             hide_index=True, use_container_width=True)

st.caption(
    "Limits: current index stock list only (survivorship bias flatters results); "
    "about 4 years of data; trades from the same day are correlated, so the "
    "'beat X% of random runs' figure is a guide, not a formal statistical test; "
    "costs are estimates; dividends ignored. BEARISH results measure the price "
    "falling. Shorting stocks overnight in India needs futures, so treat them as "
    "direction analysis. Past results do not predict the future. "
    "Analysis, not advice.")