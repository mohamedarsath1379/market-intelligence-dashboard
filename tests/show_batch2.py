import pandas as pd
from src.db import get_conn

pd.set_option("display.width", 250)
pd.set_option("display.max_colwidth", 140)
c = get_conn()
last = pd.read_sql("SELECT MAX(date) AS d FROM gold_rankings", c)["d"][0]
print(f"\n=== Batch 2 | {last} ===")

nm = pd.read_sql("SELECT symbol, name FROM instruments", c).set_index("symbol")["name"]

print("\n1) Price-level events today (all stocks):")
print(pd.read_sql("SELECT event, COUNT(*) AS stocks FROM gold_levels WHERE date=? "
                  "GROUP BY event ORDER BY stocks DESC", c, params=(last,)).to_string(index=False))

print("\n2) Strongest / weakest vs sector (5-day, normalised z-score):")
r = pd.read_sql("SELECT ranking_name, index_name, rank_pos, symbol, ROUND(value,2) AS rs_z "
                "FROM gold_rankings WHERE ranking_name IN ('rs_strongest','rs_weakest') "
                "AND index_name='NIFTYPHARMA' AND rank_pos<=5 ORDER BY ranking_name, rank_pos", c)
r["name"] = r["symbol"].map(nm)
print(r[["ranking_name", "rank_pos", "name", "rs_z"]].to_string(index=False))

print("\n3) Candidate setups (score >= minimum; each shows its evidence and risks):")
q = pd.read_sql("SELECT symbol, bull_score, bear_score, max_score, bull_components, "
                "bull_against, bear_components, bear_against FROM gold_candidates "
                "WHERE date=? AND (bull_score>=4 OR bear_score>=4)", c, params=(last,))
if q.empty:
    print("  none today")
for row in q.itertuples():
    side = "BULLISH" if row.bull_score >= 4 else "BEARISH"
    comp = row.bull_components if side == "BULLISH" else row.bear_components
    ag = row.bull_against if side == "BULLISH" else row.bear_against
    sc = row.bull_score if side == "BULLISH" else row.bear_score
    print(f"\n  {side} {nm.get(row.symbol, row.symbol)} - score {sc:.0f}/{row.max_score}")
    print(f"    evidence: {comp}")
    print(f"    against : {ag}")

print("\n4) Data status today:")
print(pd.read_sql("SELECT data_status, COUNT(*) AS stocks FROM gold_candidates WHERE date=? "
                  "GROUP BY data_status", c, params=(last,)).to_string(index=False))