"""Compare two ways of weighting index constituents against the REAL index return.

constant : today's weights applied to every past day (what we use now)
backcast : today's weights rolled back with price ratios (fixed share counts),
           so weights drift the way a real index's weights do
Error = |weighted stock return - real index return| in percentage points.
"""
import numpy as np
import pandas as pd
from src.db import get_conn, load_config


def explained_returns(px, w0, backcast):
    close = (px[px["symbol"].isin(w0.index)]
             .pivot(index="date", columns="symbol", values="close").sort_index())
    ret = (close / close.shift(1) - 1) * 100
    w0 = w0.reindex(close.columns)
    if backcast:
        q = w0 / close.ffill().iloc[-1]          # constant "share counts"
        val = close.shift(1) * q                 # value at the previous close
        w = val.div(val.sum(axis=1), axis=0)
    else:
        w = pd.DataFrame(np.tile(w0.to_numpy(), (len(close), 1)),
                         index=close.index, columns=close.columns)
    return (w * ret).sum(axis=1, min_count=1)


def summarize(idx_ret, exp):
    d = pd.DataFrame({"idx": idx_ret, "exp": exp}).dropna()
    d["err"] = (d["exp"] - d["idx"]).abs()
    d["year"] = d.index.str[:4]
    big = d[d["idx"].abs() >= 0.5]
    ratio = big["exp"] / big["idx"] * 100
    return d, {
        "days": len(d),
        "correlation": round(d["exp"].corr(d["idx"]), 4),
        "median_abs_err_pts": round(d["err"].median(), 3),
        "mean_abs_err_pts": round(d["err"].mean(), 3),
        "p90_abs_err_pts": round(d["err"].quantile(0.9), 3),
        "days_move>=0.5%": len(big),
        "explained%_p10": round(ratio.quantile(0.1), 0),
        "explained%_median": round(ratio.median(), 0),
        "explained%_p90": round(ratio.quantile(0.9), 0),
    }


def main():
    cfg = load_config()
    c = get_conn()
    px = pd.read_sql("SELECT symbol, date, close FROM silver_daily_prices", c)
    wt = pd.read_sql("SELECT index_name, symbol, weight FROM silver_index_weights", c)
    for name, ic in cfg["indices"].items():
        idx = px[px["symbol"] == ic["yf_symbol"]].set_index("date")["close"].sort_index()
        idx_ret = (idx / idx.shift(1) - 1) * 100
        w = wt[wt["index_name"] == name].set_index("symbol")["weight"]
        res, byyear = {}, {}
        for label, bc in [("constant", False), ("backcast", True)]:
            d, s = summarize(idx_ret, explained_returns(px, w, bc))
            res[label] = s
            byyear[label] = d.groupby("year")["err"].median().round(3)
        print(f"\n=== {name} ===")
        print(pd.DataFrame(res).to_string())
        print("\nMedian abs error (pct points) by year:")
        print(pd.DataFrame(byyear).to_string())


if __name__ == "__main__":
    main()