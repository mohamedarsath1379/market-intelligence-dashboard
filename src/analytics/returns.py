import pandas as pd
from src.db import get_conn


def compute(prices):
    df = prices.sort_values(["symbol", "date"]).copy()
    g = df.groupby("symbol")
    df["prev_close"] = g["close"].shift(1)
    df["pct_change"] = (df["close"] / df["prev_close"] - 1) * 100
    df["pdh"] = g["high"].shift(1)      # previous day high
    df["pdl"] = g["low"].shift(1)       # previous day low
    # average of the PREVIOUS 20 days (no look-ahead)
    df["avg_vol_20"] = g["volume"].transform(
        lambda s: s.shift(1).rolling(20).mean())
    return df[["symbol", "date", "close", "prev_close", "pct_change",
               "pdh", "pdl", "volume", "avg_vol_20"]]


def run():
    conn = get_conn()
    prices = pd.read_sql("SELECT * FROM silver_daily_prices", conn)
    out = compute(prices)
    conn.execute("DELETE FROM gold_returns")
    out.to_sql("gold_returns", conn, if_exists="append", index=False)
    conn.commit()
    print(f"gold_returns: {len(out)} rows")


if __name__ == "__main__":
    run()