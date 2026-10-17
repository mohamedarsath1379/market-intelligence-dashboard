import pandas as pd
from src.db import get_conn, load_config
from src.analytics.levels import flags


def run():
    cfg = load_config()
    mult = cfg["thresholds"]["breakout_volume_multiple"]
    conn = get_conn()

    stocks = pd.read_sql("SELECT symbol, name FROM instruments WHERE kind='stock'", conn)
    ret = pd.read_sql("SELECT * FROM gold_returns", conn)
    ret = ret[ret["symbol"].isin(stocks["symbol"])]
    last = ret["date"].max()

    today = flags(ret[ret["date"] == last], mult)
    trend = pd.read_sql("SELECT symbol, trend FROM gold_trend WHERE date=?",
                        conn, params=(last,))
    rs = pd.read_sql(
        "SELECT index_name, symbol, rs FROM gold_relative_strength WHERE date=?",
        conn, params=(last,))
    # prefer the sector index over NIFTY50 when a stock is in both
    rs["pri"] = (rs["index_name"] == "NIFTY50").astype(int)
    rs = rs.sort_values("pri").drop_duplicates("symbol")[["symbol", "index_name", "rs"]]

    cand = (today[today["breakout"] | today["breakdown"]]
            .merge(trend, on="symbol", how="left")
            .merge(rs, on="symbol", how="left")
            .merge(stocks, on="symbol", how="left"))

    rows = []
    for r in cand.itertuples():
        if r.breakout:
            kind, tag, level, sign = "BREAKOUT", "PDH", r.pdh, ">"
        else:
            kind, tag, level, sign = "BREAKDOWN", "PDL", r.pdl, "<"
        reason = (f"close {r.close:.2f} {sign} {tag} {level:.2f}; "
                  f"volume {r.vol_ratio:.1f}x 20-day avg; trend {r.trend}")
        if pd.notna(r.rs):
            reason += f"; RS {r.rs:+.1f}% vs {r.index_name}"
        rows.append((last, r.symbol, kind, reason))

    conn.execute("DELETE FROM gold_signals WHERE date=?", (last,))
    conn.executemany("INSERT INTO gold_signals VALUES (?,?,?,?)", rows)
    conn.commit()

    print(f"Scanner date: {last} | candidates: {len(rows)}")
    for date, sym, kind, reason in rows:
        print(f"  {kind:9} {sym:14} {reason}")


if __name__ == "__main__":
    run()