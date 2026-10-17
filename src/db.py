import sqlite3
import pathlib
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent


def load_config():
    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_conn():
    cfg = load_config()
    path = ROOT / cfg["db_path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript((ROOT / "db" / "schema.sql").read_text(encoding="utf-8"))
    return conn