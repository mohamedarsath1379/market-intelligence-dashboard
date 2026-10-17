import numpy as np
import pandas as pd
from src.db import get_conn

BULL_OK = {"breakout confirmed", "retest held (above PDH)"}
BEAR_OK = {"breakdown confirmed", "retest held (below PDL)"}


def _load_prices(conn):
    px = pd.read_sql("SELECT symbol, date, open, high, low, close "
                     "FROM silver_daily_prices WHERE symbol NOT LIKE '^%' "
                     "ORDER BY symbol, date", conn)
    data = {}
    for sym, g in px.groupby("symbol"):
        data[sym] = dict(
            dates=g["date"].tolist(),
            idx={d: i for i, d in enumerate(g["date"])},
            o=g["open"].to_numpy(float), h=g["high"].to_numpy(float),
            l=g["low"].to_numpy(float), c=g["close"].to_numpy(float))
    return data


def simulate(d, i_sig, direction, hold, stop, cost):
    """Signal known at close of day i_sig. Enter at NEXT day's open (no look-ahead).
    direction: +1 long, -1 short. Returns (ret_pct, exit_reason, entry_i, exit_i) or None."""
    e = i_sig + 1
    x = e + hold - 1
    if x >= len(d["c"]):
        return None
    entry = d["o"][e]
    if not entry or entry != entry:
        return None
    reason, exit_px, exit_i = "time", d["c"][x], x
    if stop > 0:
        for j in range(e, x + 1):
            if direction == 1:
                sp = entry * (1 - stop / 100)
                if d["l"][j] <= sp:
                    exit_px = min(sp, d["o"][j]) if j > e else sp
                    reason, exit_i = "stop", j
                    break
            else:
                sp = entry * (1 + stop / 100)
                if d["h"][j] >= sp:
                    exit_px = max(sp, d["o"][j]) if j > e else sp
                    reason, exit_i = "stop", j
                    break
    ret = direction * (exit_px / entry - 1) * 100 - 2 * cost
    return ret, reason, e, exit_i


def _returns_by_date(data, c, direction, hold, stop, cost):
    """Simulate EVERY valid entry once. Returns {date: array of returns}."""
    out = {}
    for r in c.itertuples():
        d = data[r.symbol]
        i = d["idx"].get(r.date)
        if i is None:
            continue
        res = simulate(d, i, direction, hold, stop, cost)
        if res is not None:
            out.setdefault(r.date, []).append(res[0])
    return {k: np.array(v) for k, v in out.items()}


def _date_matched_baseline(trades_side, rets_by_date, n_sims, rng):
    """For each real trade, pick a random stock on the SAME signal date
    (same direction, hold, stop, cost). Repeat n_sims times."""
    arrays = [rets_by_date[d] for d in trades_side["signal_date"]
              if d in rets_by_date]
    if not arrays:
        return None
    lens = np.array([len(a) for a in arrays])
    offsets = np.concatenate([[0], np.cumsum(lens)[:-1]])
    flat = np.concatenate(arrays)
    n = len(arrays)
    means = np.empty(n_sims)
    for s in range(n_sims):
        pick = (rng.random(n) * lens).astype(int)
        means[s] = flat[offsets + pick].mean()
    return means


def run_setup_backtest(hold=5, stop=3.0, cost=0.1, min_score=4,
                       n_sims=1000, seed=42):
    conn = get_conn()
    data = _load_prices(conn)

    c = pd.read_sql("""SELECT c.symbol, c.date, c.bull_score, c.bear_score,
                              c.max_score, c.data_status, l.event
                       FROM gold_candidates c
                       LEFT JOIN gold_levels l
                         ON l.symbol = c.symbol AND l.date = c.date""", conn)
    c = c[c["symbol"].isin(data.keys())]
    c = c[c["data_status"].fillna("ok") == "ok"]

    mt = pd.read_sql("SELECT date, trend FROM gold_market_trend "
                     "WHERE index_name='NIFTY50'", conn).set_index("date")["trend"]

    # ---- real setups ----
    rows = []
    for r in c.itertuples():
        ev = r.event if r.event else "none"
        long_ok = r.bull_score >= min_score and ev in BULL_OK
        short_ok = r.bear_score >= min_score and ev in BEAR_OK
        if not (long_ok or short_ok):
            continue
        if long_ok and short_ok:
            long_ok = r.bull_score >= r.bear_score
        direction = 1 if long_ok else -1
        d = data[r.symbol]
        i = d["idx"].get(r.date)
        if i is None:
            continue
        res = simulate(d, i, direction, hold, stop, cost)
        if res is None:
            continue
        ret, reason, e, x = res
        rows.append(dict(
            symbol=r.symbol, signal_date=r.date, entry_date=d["dates"][e],
            exit_date=d["dates"][x], side="BULLISH" if direction == 1 else "BEARISH",
            event=ev, nifty50_trend=mt.get(r.date, "n/a"),
            ret_pct=ret, exit_reason=reason))
    trades = pd.DataFrame(rows)

    # ---- date-matched random baseline ----
    rng = np.random.default_rng(seed)
    base = {}
    if len(trades):
        for side, direction in (("BULLISH", 1), ("BEARISH", -1)):
            ts = trades[trades["side"] == side]
            if ts.empty:
                continue
            rets = _returns_by_date(data, c, direction, hold, stop, cost)
            means = _date_matched_baseline(ts, rets, n_sims, rng)
            if means is None:
                continue
            actual = ts["ret_pct"].mean()
            base[side] = dict(
                actual=actual, random_mean=means.mean(),
                p5=np.percentile(means, 5), p95=np.percentile(means, 95),
                edge=actual - means.mean(),
                pct_random_beaten=(means < actual).mean() * 100)
    return trades, base


def summarize(t):
    if len(t) == 0:
        return {}
    w, l = t[t["ret_pct"] > 0]["ret_pct"], t[t["ret_pct"] <= 0]["ret_pct"]
    pf = w.sum() / abs(l.sum()) if len(l) and l.sum() != 0 else float("nan")
    return {"trades": len(t),
            "win_rate_%": round((t["ret_pct"] > 0).mean() * 100, 1),
            "avg_return_%": round(t["ret_pct"].mean(), 3),
            "median_return_%": round(t["ret_pct"].median(), 3),
            "avg_win_%": round(w.mean(), 2) if len(w) else 0,
            "avg_loss_%": round(l.mean(), 2) if len(l) else 0,
            "profit_factor": round(pf, 2)}