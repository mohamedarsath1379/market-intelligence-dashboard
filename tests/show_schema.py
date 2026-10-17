from src.db import get_conn

c = get_conn()
tables = [r[0] for r in c.execute(
    "SELECT name FROM sqlite_master WHERE type IN ('table','view') ORDER BY name")]
for t in tables:
    cols = [r[1] for r in c.execute(f"PRAGMA table_info({t})")]
    n = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"\n{t} ({n} rows)")
    print("  columns:", ", ".join(cols))