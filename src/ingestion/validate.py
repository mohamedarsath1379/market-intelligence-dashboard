import pandas as pd
from src.db import get_conn


def run():
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM bronze_daily_prices", conn)
    total = len(df)

    dup = df.duplicated(["symbol", "date"]).sum()
    df = df.drop_duplicates(["symbol", "date"])

    bad_mask = (df.high < df.low) | (df.close <= 0) | df.close.isna()
    bad = int(bad_mask.sum())
    df = df[~bad_mask]

    counts = df.groupby("symbol").size()
    short = counts[counts < counts.median() * 0.9]

    is_index = df.symbol.str.startswith("^")
    zero_vol = int(((df.volume == 0) & ~is_index).sum())

    print(f"bronze rows: {total}")
    print(f"duplicates removed: {dup}")
    print(f"bad rows removed: {bad}")
    print(f"zero-volume stock days (kept, just flagged): {zero_vol}")
    print("symbols with missing history:")
    print(short if len(short) else "  none")

    clean = df[["symbol", "date", "open", "high", "low", "close", "volume"]]
    conn.execute("DELETE FROM silver_daily_prices")
    conn.executemany(
        "INSERT INTO silver_daily_prices VALUES (?,?,?,?,?,?,?)",
        clean.values.tolist())
    conn.commit()
    print(f"silver rows saved: {len(clean)}")


if __name__ == "__main__":
    run()