import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import plotly.express as px
import streamlit as st
from dashboard.helpers import q, index_names, index_symbol, latest_date, data_banner  # NEW: data_banner

st.title("Index Drivers")
data_banner()  # NEW
idx = st.selectbox("Index", index_names(), index=1)
last = latest_date()
dates = q("SELECT DISTINCT date FROM gold_contribution WHERE index_name=? "
          "ORDER BY date DESC LIMIT 60", (idx,))["date"].tolist()
day = st.selectbox("Date", dates, index=0)

move = q("SELECT pct_change FROM gold_returns WHERE symbol=? AND date=?",
         (index_symbol(idx), day))
if len(move):
    st.metric(f"{idx} move on {day}", f"{move['pct_change'][0]:.2f}%")

c = q("""SELECT i.name, c.weight*100 AS weight_pct, c.pct_change, c.contribution
         FROM gold_contribution c JOIN instruments i ON i.symbol=c.symbol
         WHERE c.index_name=? AND c.date=? ORDER BY c.contribution DESC""",
      (idx, day))
st.subheader("Contribution = weight x stock move")
fig = px.bar(c, x="contribution", y="name", orientation="h",
             color="contribution", color_continuous_scale="RdYlGn",
             color_continuous_midpoint=0)
fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=600)
st.plotly_chart(fig, use_container_width=True)
st.dataframe(c.round(3), use_container_width=True)

st.subheader("Breadth (advances vs declines)")
b = q("SELECT date, advances, declines FROM gold_breadth "
      "WHERE index_name=? ORDER BY date DESC LIMIT 60", (idx,)).sort_values("date")
st.plotly_chart(
    px.bar(b, x="date", y=["advances", "declines"], barmode="group",
           color_discrete_map={"advances": "#22c55e", "declines": "#ef4444"}),
    use_container_width=True)
st.caption("Weights are approximate (market-cap based), so contributions "
           "will not add up exactly to the official index move.")