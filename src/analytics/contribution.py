import pandas as pd
from src.db import get_conn


def run():
    conn = get_conn()
    ret = pd.read_sql("SELECT symbol, date, pct_change FROM gold_returns", conn)
    ret = ret.dropna(subset=["pct_change"])
    w = pd.read_sql(
        "SELECT index_name, symbol, weight FROM silver_index_weights", conn)
    out = ret.merge(w, on="symbol")
    out["contribution"] = out["weight"] * out["pct_change"]
    out = out[["index_name", "date", "symbol", "weight",
               "pct_change", "contribution"]]
    conn.execute("DELETE FROM gold_contribution")
    out.to_sql("gold_contribution", conn, if_exists="append", index=False)
    conn.commit()
    print(f"gold_contribution: {len(out)} rows")


if __name__ == "__main__":
    run()