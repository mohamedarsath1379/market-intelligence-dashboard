import sys
import datetime as dt
import requests
import pandas as pd
from src.db import ROOT, get_conn, load_config

BULL_OK = {"breakout confirmed", "retest held (above PDH)"}
BEAR_OK = {"breakdown confirmed", "retest held (below PDL)"}
MIN_SCORE = 4
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def load_env():
    env = {}
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def short(name):
    return str(name).replace(" Ltd.", "").replace(" Limited", "")


def build_message(conn, last):
    cfg = load_config()
    lines = [f"MARKET SUMMARY - {last}", ""]

    # ---- index moves ----
    for name, c in cfg["indices"].items():
        sym = c["yf_symbol"]
        r = pd.read_sql("SELECT close, pct_change FROM gold_returns "
                        "WHERE symbol=? AND date=?", conn, params=(sym, last))
        if r.empty:
            continue
        t = pd.read_sql("SELECT trend FROM gold_trend WHERE symbol=? AND date=?",
                        conn, params=(sym, last))
        b = pd.read_sql("SELECT advances, declines FROM gold_breadth "
                        "WHERE index_name=? AND date=?", conn, params=(name, last))
        trend = t["trend"][0] if len(t) else "n/a"
        txt = f"{name}: {r['close'][0]:,.2f} ({r['pct_change'][0]:+.2f}%), trend {trend}"
        if len(b):
            txt += f", {int(b['advances'][0])} up / {int(b['declines'][0])} down"
        lines.append(txt)

    # ---- setups vs watchlist ----
    c = pd.read_sql("""
        SELECT i.name, c.bull_score, c.bear_score, c.max_score, l.event
        FROM gold_candidates c
        JOIN instruments i ON i.symbol = c.symbol
        LEFT JOIN gold_levels l ON l.symbol = c.symbol AND l.date = c.date
        WHERE c.date = ? AND (c.bull_score >= ? OR c.bear_score >= ?)""",
        conn, params=(last, MIN_SCORE, MIN_SCORE))
    setups, watch = [], []
    for r in c.itertuples():
        bull = r.bull_score >= r.bear_score
        score = r.bull_score if bull else r.bear_score
        ev = r.event if r.event else "none"
        item = (f"{'BULL' if bull else 'BEAR'} {short(r.name)} "
                f"{score:.0f}/{r.max_score:.0f} ({ev})")
        ok = ev in (BULL_OK if bull else BEAR_OK)
        (setups if ok else watch).append(item)
    setups.sort()
    watch.sort()
    lines += ["", f"SETUPS ({len(setups)}) - confirmed level + volume:"]
    lines += [f"- {s}" for s in setups] or ["- none"]
    lines += ["", f"WATCHLIST ({len(watch)}) - good score, no confirmed event:"]
    lines += [f"- {w}" for w in watch] or ["- none"]

    # ---- contributors / draggers ----
    for name in cfg["indices"]:
        d = pd.read_sql("""
            SELECT i.name, c.contribution FROM gold_contribution c
            JOIN instruments i ON i.symbol = c.symbol
            WHERE c.index_name=? AND c.date=? ORDER BY c.contribution DESC""",
            conn, params=(name, last))
        if d.empty:
            continue
        top = ", ".join(f"{short(n)} {v:+.3f}" for n, v in
                        zip(d["name"].head(3), d["contribution"].head(3)))
        bot = ", ".join(f"{short(n)} {v:+.3f}" for n, v in
                        zip(d["name"].tail(3).iloc[::-1], d["contribution"].tail(3).iloc[::-1]))
        lines += ["", f"{name} drivers (weight x move, approx weights)",
                  f"Up: {top}", f"Down: {bot}"]

    lines += ["", "Analysis only, not investment advice. End-of-day data from Yahoo Finance."]
    return "\n".join(lines)[:4000]


def already_sent(conn, last):
    n = conn.execute("SELECT COUNT(*) FROM alerts WHERE date=? AND sent=1",
                     (last,)).fetchone()[0]
    return n > 0


def send(text, token, chat_id):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    r = requests.post(url, data={"chat_id": chat_id, "text": text}, timeout=30)
    if not r.ok:
        raise RuntimeError(f"Telegram error {r.status_code}: {r.text[:200]}")


def run(dry=False, force=False):
    conn = get_conn()
    last = pd.read_sql("SELECT MAX(date) AS d FROM gold_returns", conn)["d"][0]

    now = dt.datetime.now(IST)
    mins = now.hour * 60 + now.minute
    if (not force and last == now.strftime("%Y-%m-%d")
            and now.weekday() < 5 and mins < 15 * 60 + 45):
        print(f"{last} is still provisional (market open). Not sending. "
              "Use --force to override.")
        return

    if not dry and not force and already_sent(conn, last):
        print(f"Alert for {last} was already sent. Skipping (use --force to resend).")
        return

    msg = build_message(conn, last)
    print(msg)
    if dry:
        print("\n[dry run] nothing sent.")
        return

    env = load_env()
    token, chat = env.get("TELEGRAM_TOKEN"), env.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("\n[skip] TELEGRAM_TOKEN / TELEGRAM_CHAT_ID missing in .env")
        return
    send(msg, token, chat)
    conn.execute("INSERT INTO alerts VALUES (?,?,1)", (last, msg))
    conn.commit()
    print(f"\nSent to Telegram for {last}.")


if __name__ == "__main__":
    run(dry="--dry" in sys.argv, force="--force" in sys.argv)