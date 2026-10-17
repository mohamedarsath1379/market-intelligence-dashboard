import pandas as pd
import yfinance as yf
from src.db import ROOT, load_config, get_conn


def download(symbols, start):
    df = yf.download(symbols, start=start, auto_adjust=False,
                     group_by="ticker", progress=False, threads=True)
    frames = []
    for s in symbols:
        try:
            d = df[s].dropna(subset=["Close"]).reset_index()
        except KeyError:
            print(f"[warn] no data for {s}")
            continue
        d = d[["Date", "Open", "High", "Low", "Close", "Volume"]].copy()
        d["symbol"] = s
        d["date"] = pd.to_datetime(d["Date"]).dt.strftime("%Y-%m-%d")
        frames.append(d[["symbol", "date", "Open", "High", "Low",
                         "Close", "Volume"]])
    if not frames:
        raise RuntimeError("No price data downloaded. Check internet/symbols.")
    return pd.concat(frames, ignore_index=True)


def run():
    cfg = load_config()
    conn = get_conn()
    symbols = [r[0] for r in conn.execute("SELECT symbol FROM instruments")]
    data = download(symbols, cfg["history_start"])

    # bronze file on disk (never edited)
    raw_dir = ROOT / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    stamp = pd.Timestamp.today().strftime("%Y%m%d")
    data.to_csv(raw_dir / f"prices_{stamp}.csv", index=False)

    # bronze table
    loaded_at = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = [tuple(r) + (loaded_at,) for r in data.values.tolist()]
    conn.executemany(
        "INSERT OR REPLACE INTO bronze_daily_prices VALUES (?,?,?,?,?,?,?,?)",
        rows)
    conn.commit()
    print(f"{len(rows)} bronze rows saved for {len(symbols)} symbols")


if __name__ == "__main__":
    run()