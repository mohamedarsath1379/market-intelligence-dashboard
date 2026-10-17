import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots
from dashboard.helpers import q, latest_date, data_banner  # NEW: data_banner

st.title("Stock Detail")
data_banner()  # NEW

stocks = q("SELECT symbol, name FROM instruments WHERE kind='stock' ORDER BY name")
label = st.selectbox("Stock", stocks["name"].tolist())
sym = stocks.loc[stocks["name"] == label, "symbol"].iloc[0]
period = st.selectbox("Period", ["3 months", "6 months", "1 year", "All"], index=1)
days = {"3 months": 63, "6 months": 126, "1 year": 252, "All": 100000}[period]

last = latest_date()

# ---- summary numbers ----
s = q("""SELECT r.close, r.pct_change, r.pdh, r.pdl, r.volume, r.avg_vol_20, t.trend
         FROM gold_returns r
         LEFT JOIN gold_trend t ON t.symbol = r.symbol AND t.date = r.date
         WHERE r.symbol=? AND r.date=?""", (sym, last))

pdh = pdl = None
if len(s) == 0:
    st.warning(f"No data for {label} on {last}.")
else:
    r = s.iloc[0]
    pdh, pdl = r["pdh"], r["pdl"]
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Close", f"{r['close']:,.0f}", f"{r['pct_change']:.2f}%")
    c2.caption("Trend")
    c2.markdown(f"#### {r['trend']}")
    if r["avg_vol_20"] and r["avg_vol_20"] > 0:
        c3.metric("Volume vs 20-day avg", f"{r['volume'] / r['avg_vol_20']:.1f}x")
    c4.metric("PDH", f"{r['pdh']:,.1f}")
    c5.metric("PDL", f"{r['pdl']:,.1f}")

    rs = q("""SELECT index_name, rs FROM gold_relative_strength
              WHERE symbol=? AND date=?""", (sym, last))
    for row in rs.itertuples():
        st.write(f"Relative strength (20 days) vs **{row.index_name}**: "
                 f"**{row.rs:+.2f}%**")

    sig = q("SELECT signal, reason FROM gold_signals WHERE symbol=? AND date=?",
            (sym, last))
    if len(sig):
        st.success(f"{sig['signal'][0]}: {sig['reason'][0]}")
    else:
        st.info("No breakout/breakdown signal on the latest day.")

    # ---- NEW: setup score with evidence ----
    st.subheader("Setup score (today)")
    cand = q("""SELECT bull_score, bear_score, max_score, bull_components,
                       bull_against, bear_components, bear_against
                FROM gold_candidates WHERE symbol=? AND date=?""", (sym, last))
    if len(cand):
        k = cand.iloc[0]
        a, b = st.columns(2)
        a.metric("Bullish score", f"{k['bull_score']:.0f}/{k['max_score']}")
        b.metric("Bearish score", f"{k['bear_score']:.0f}/{k['max_score']}")
        side = "bull" if k["bull_score"] >= k["bear_score"] else "bear"
        st.write(f"**Stronger side: {side.upper()}**")
        st.write("**Evidence:** " + str(k[f"{side}_components"]))
        st.write("**Against:** " + str(k[f"{side}_against"]))
    else:
        st.info("No score for this stock today.")

# ---- price chart ----
df = q("""SELECT p.date, p.open, p.high, p.low, p.close, p.volume,
                 t.sma_fast, t.sma_slow
          FROM silver_daily_prices p
          LEFT JOIN gold_trend t ON t.symbol = p.symbol AND t.date = p.date
          WHERE p.symbol=? ORDER BY p.date""", (sym,)).tail(days)

fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                    row_heights=[0.75, 0.25], vertical_spacing=0.03)
fig.add_trace(go.Candlestick(x=df["date"], open=df["open"], high=df["high"],
                             low=df["low"], close=df["close"], name="Price"),
              row=1, col=1)
fig.add_trace(go.Scatter(x=df["date"], y=df["sma_fast"], name="SMA 20",
                         line=dict(color="#f59e0b", width=1.5)), row=1, col=1)
fig.add_trace(go.Scatter(x=df["date"], y=df["sma_slow"], name="SMA 50",
                         line=dict(color="#38bdf8", width=1.5)), row=1, col=1)
# NEW: PDH / PDL lines
if pdh is not None and pdh == pdh:   # pdh == pdh is False for NaN
    fig.add_hline(y=pdh, line_dash="dot", line_color="green",
                  annotation_text="PDH", row=1, col=1)
if pdl is not None and pdl == pdl:
    fig.add_hline(y=pdl, line_dash="dot", line_color="red",
                  annotation_text="PDL", row=1, col=1)
fig.add_trace(go.Bar(x=df["date"], y=df["volume"], name="Volume",
                     marker_color="#64748b"), row=2, col=1)
fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
fig.update_layout(height=650, xaxis_rangeslider_visible=False,
                  margin=dict(t=20, b=20))
st.plotly_chart(fig, use_container_width=True)
st.caption("SMA lines start only after enough history. Recently listed stocks "
           "will have shorter lines. Analysis only, not investment advice.")

# ---- NEW: recent price-level events ----
st.subheader("Recent price-level events")
ev = q("""SELECT date, event FROM gold_levels
          WHERE symbol=? AND event <> 'none'
          ORDER BY date DESC LIMIT 10""", (sym,))
if len(ev):
    st.dataframe(ev, use_container_width=True, hide_index=True)
else:
    st.info("No breakout/breakdown events recently.")