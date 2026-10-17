import pandas as pd
from src.db import get_conn

c = get_conn()
for idx in ["NIFTY50", "NIFTYPHARMA"]:
    s = pd.read_sql("SELECT date, explained_pct FROM gold_contrib_summary "
                    "WHERE index_name=? AND explained_pct IS NOT NULL",
                    c, params=(idx,))
    print(f"\n=== {idx} | days with a clear move: {len(s)} ===")
    print(s["explained_pct"].describe(percentiles=[.1, .5, .9]).round(1).to_string())
    s["year"] = s["date"].str[:4]
    print("\nMedian explained_pct by year:")
    print(s.groupby("year")["explained_pct"].median().round(1).to_string())