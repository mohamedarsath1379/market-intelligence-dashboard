import pandas as pd
from src.db import get_conn, load_config


def run():
    cfg = load_config()
    n = cfg.get("rs_window", 20)          # 20 trading days
    conn = get_conn()
    px = pd.read_sql("SELECT symbol, date, close FROM silver_daily_prices", conn)
    wide = px.pivot(index="date", columns="symbol", values="close").sort_index()
    ret_n = (wide / wide.shift(n) - 1) * 100

    w = pd.read_sql("SELECT index_name, symbol FROM silver_index_weights", conn)
    nifty_sym = cfg["indices"]["NIFTY50"]["yf_symbol"]

    parts = []
    for idx_name, grp in w.groupby("index_name"):
        idx_sym = cfg["indices"][idx_name]["yf_symbol"]
        if idx_sym not in ret_n.columns:
            print(f"[warn] no index data for {idx_name}")
            continue
        syms = [s for s in grp["symbol"] if s in ret_n.columns]
        d = (ret_n[syms].reset_index()
             .melt(id_vars="date", var_name="symbol", value_name="stock_ret"))
        d["index_ret"] = d["date"].map(ret_n[idx_sym])
        d["nifty_ret"] = d["date"].map(ret_n[nifty_sym])
        d["rs"] = d["stock_ret"] - d["index_ret"]
        d["rs_vs_nifty50"] = d["stock_ret"] - d["nifty_ret"]
        d["index_name"] = idx_name
        parts.append(d.dropna(subset=["stock_ret", "index_ret"]))

    out = pd.concat(parts, ignore_index=True)[
        ["index_name", "date", "symbol", "stock_ret", "index_ret",
         "rs", "rs_vs_nifty50"]]
    conn.execute("DELETE FROM gold_relative_strength")
    out.to_sql("gold_relative_strength", conn, if_exists="append", index=False)
    conn.commit()
    print(f"gold_relative_strength: {len(out)} rows")


if __name__ == "__main__":
    run()