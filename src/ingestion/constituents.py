import requests
import pandas as pd
import yfinance as yf
from src.db import ROOT, load_config, get_conn

HEADERS = {"User-Agent": "Mozilla/5.0"}


def fetch_constituents(index_name, url):
    raw_dir = ROOT / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    local = raw_dir / f"constituents_{index_name}.csv"
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        local.write_bytes(r.content)          # bronze: raw file saved
    except Exception as e:
        if not local.exists():
            raise RuntimeError(
                f"Download failed ({e}). Download the CSV manually from "
                f"niftyindices.com and save it as {local}")
        print(f"[warn] download failed, using saved file {local}")
    df = pd.read_csv(local)
    df["yf_symbol"] = df["Symbol"].str.strip() + ".NS"
    return df[["Company Name", "Industry", "yf_symbol"]]


def approx_weights(symbols, index_name=None):
    """Approximate weights from market cap, NOT official free-float weights.
    If Yahoo fails for some stocks (common on cloud servers), use the saved
    fallback file so no stock is silently dropped."""
    caps = {}
    for s in symbols:
        try:
            caps[s] = yf.Ticker(s).fast_info["market_cap"]
        except Exception:
            caps[s] = None
    ser = pd.Series(caps, dtype=float).dropna()

    fb_path = ROOT / "data" / "raw" / "weights_fallback.csv"
    missing = [s for s in symbols if s not in ser.index]

    if missing and fb_path.exists() and index_name:
        fb = pd.read_csv(fb_path)
        fb = fb[fb["index_name"] == index_name].set_index("symbol")["weight"]
        fb = fb.reindex(symbols).dropna()
        print(f"[warn] {index_name}: market cap missing for {len(missing)} "
              f"stocks, using saved weights")
        if len(missing) > 3 or ser.empty:
            # too many failures: use the saved weights for everything (consistent)
            return fb / fb.sum()
        # few failures: keep live caps, fill the gaps from saved weights
        fill = fb.reindex(missing).dropna()
        live = ser / ser.sum() * (1 - fill.sum())
        out = pd.concat([live, fill])
        return out / out.sum()

    if ser.empty:
        raise RuntimeError(
            f"No market caps for {index_name} and no weights_fallback.csv found.")
    return ser / ser.sum()


def run():
    cfg = load_config()
    conn = get_conn()
    today = pd.Timestamp.today().strftime("%Y-%m-%d")
    for idx, c in cfg["indices"].items():
        df = fetch_constituents(idx, c["constituents_url"])
        conn.execute("INSERT OR REPLACE INTO instruments VALUES (?,?,?)",
                     (c["yf_symbol"], idx, "index"))
        for _, r in df.iterrows():
            conn.execute("INSERT OR REPLACE INTO instruments VALUES (?,?,?)",
                         (r["yf_symbol"], r["Company Name"], "stock"))
        w = approx_weights(df["yf_symbol"].tolist(), idx)
        for sym, wt in w.items():
            conn.execute(
                "INSERT OR REPLACE INTO silver_index_weights VALUES (?,?,?,?)",
                (idx, sym, float(wt), today))
        conn.commit()
        print(f"{idx}: {len(df)} stocks saved, {len(w)} with weights")


if __name__ == "__main__":
    run()