import numpy as np
import pandas as pd
from src.db import get_conn


def run():
    conn = get_conn()
    ret = pd.read_sql("SELECT symbol, date, pct_change FROM gold_returns", conn)
    ret = ret.dropna(subset=["pct_change"])
    w = pd.read_sql("SELECT index_name, symbol FROM silver_index_weights", conn)
    m = ret.merge(w, on="symbol")
    out = (m.groupby(["index_name", "date"])["pct_change"]
             .agg(advances=lambda s: int((s > 0).sum()),
                  declines=lambda s: int((s < 0).sum()),
                  unchanged=lambda s: int((s == 0).sum()))
             .reset_index())
    out["ad_ratio"] = out["advances"] / out["declines"].replace(0, np.nan)
    conn.execute("DELETE FROM gold_breadth")
    out.to_sql("gold_breadth", conn, if_exists="append", index=False)
    conn.commit()
    print(f"gold_breadth: {len(out)} rows")


if __name__ == "__main__":
    run()