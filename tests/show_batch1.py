import pandas as pd
from src.db import get_conn

IDX = "NIFTYPHARMA"
c = get_conn()
last = pd.read_sql("SELECT MAX(date) AS d FROM gold_market_trend WHERE index_name=?",
                   c, params=(IDX,))["d"][0]
print(f"\n=== {IDX} | {last} ===")

t = pd.read_sql("SELECT trend, bull_votes, bear_votes, conditions FROM gold_market_trend "
                "WHERE index_name=? AND date=?", c, params=(IDX, last)).iloc[0]
print(f"\nTrend: {t['trend']}  (bull votes {t['bull_votes']}, bear votes {t['bear_votes']})")
print("Conditions:", t["conditions"])

print("\nIndex move explained by our weights:")
print(pd.read_sql("SELECT ROUND(index_pts,1) AS index_pts, ROUND(explained_pts,1) AS explained_pts, "
                  "ROUND(explained_pct,0) AS explained_pct, ROUND(top_n_share_pct,0) AS top3_share_pct "
                  "FROM gold_contrib_summary WHERE index_name=? AND date=?",
                  c, params=(IDX, last)).to_string(index=False))

print("\nContribution in index points (most negative first):")
print(pd.read_sql("""SELECT i.name, ROUND(c.weight*100,2) AS weight_pct,
                            ROUND(c.pct_change,2) AS pct_change,
                            ROUND(c.contrib_pts,1) AS pts,
                            ROUND(c.share_of_move_pct,1) AS share_of_move_pct
                     FROM gold_contrib_points c JOIN instruments i ON i.symbol=c.symbol
                     WHERE c.index_name=? AND c.date=? ORDER BY c.contrib_pts""",
                  c, params=(IDX, last)).to_string(index=False))

print("\nBreadth:")
print(pd.read_sql("SELECT advances, declines, ROUND(pct_above_open,0) AS pct_above_open, "
                  "ROUND(pct_above_sma20,0) AS pct_above_sma20, "
                  "ROUND(pct_above_sma50,0) AS pct_above_sma50, divergence, narrow_flag "
                  "FROM gold_breadth_detail WHERE index_name=? AND date=?",
                  c, params=(IDX, last)).to_string(index=False))