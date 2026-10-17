import pandas as pd
from src.db import get_conn

df = pd.read_sql(
    "SELECT date, close, prev_close, pct_change FROM gold_returns "
    "WHERE symbol='SUNPHARMA.NS' ORDER BY date DESC LIMIT 3",
    get_conn())
print(df)

r = df.iloc[0]
manual = (r["close"] / r["prev_close"] - 1) * 100
print("\nFrom database :", round(r["pct_change"], 4))
print("Manual check  :", round(manual, 4))
print("MATCH" if abs(manual - r["pct_change"]) < 0.0001 else "MISMATCH")