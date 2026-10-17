import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pandas as pd
from src.db import get_conn, load_config

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 20)

IDX = "NIFTYPHARMA"
conn = get_conn()
cfg = load_config()
idx_sym = cfg["indices"][IDX]["yf_symbol"]

last = pd.read_sql("SELECT MAX(date) AS d FROM gold_contribution WHERE index_name=?",
                   conn, params=(IDX,))["d"][0]
idx_move = pd.read_sql("SELECT pct_change FROM gold_returns WHERE symbol=? AND date=?",
                       conn, params=(idx_sym, last))["pct_change"][0]
print(f"\n=== {IDX} | {last} | index move: {idx_move:.2f}% ===")

print("\nTop contributors / draggers (weight x move):")
c = pd.read_sql("""
    SELECT i.name, ROUND(c.weight*100,2) AS weight_pct,
           ROUND(c.pct_change,2) AS pct_change,
           ROUND(c.contribution,3) AS contribution
    FROM gold_contribution c JOIN instruments i ON i.symbol=c.symbol
    WHERE c.index_name=? AND c.date=? ORDER BY c.contribution DESC""",
    conn, params=(IDX, last))
print(pd.concat([c.head(5), c.tail(5)]).to_string(index=False))

print("\nBreadth:")
print(pd.read_sql("SELECT advances, declines, unchanged, ROUND(ad_ratio,2) AS ad_ratio "
                  "FROM gold_breadth WHERE index_name=? AND date=?",
                  conn, params=(IDX, last)).to_string(index=False))

print("\nRelative strength vs index (20 days), strongest 5:")
print(pd.read_sql("""
    SELECT i.name, ROUND(r.stock_ret,2) AS stock_20d, ROUND(r.index_ret,2) AS index_20d,
           ROUND(r.rs,2) AS rs
    FROM gold_relative_strength r JOIN instruments i ON i.symbol=r.symbol
    WHERE r.index_name=? AND r.date=? ORDER BY r.rs DESC LIMIT 5""",
    conn, params=(IDX, last)).to_string(index=False))

print("\nScanner signals today:")
s = pd.read_sql("SELECT symbol, signal, reason FROM gold_signals WHERE date=?",
                conn, params=(last,))
print(s.to_string(index=False) if len(s) else "  none")