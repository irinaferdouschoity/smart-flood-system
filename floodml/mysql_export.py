"""Export the district data to MySQL (tables with the prefix bd_).

    python -m floodml export-mysql            # everything
    python -m floodml export-mysql --only daily --since 2026-01-01

Tables (created automatically, safe to run again - rows are updated, never duplicated):
    bd_locations      64 districts + 6 upstream stations
    bd_daily_data     one row per location per day: IMERG + NASA POWER rainfall, weather, soil wetness
    bd_flood_events   the documented flood events (with source URLs)
    bd_flood_days     one row per flooded district-day (the labels)
    bd_predictions    model output per district per "as of" date (history is kept)
    bd_latest_risk    VIEW: newest risk of every district, ready to query
"""
import math
import os
from datetime import date, timedelta
from urllib.parse import unquote, urlparse

import pandas as pd

from . import config

DAILY_COLUMNS = {
    "IMERG_PRECTOT": "imerg_precip", "PRECTOTCORR": "pcorr_precip",
    "T2M": "t2m", "T2M_MAX": "t2m_max", "T2M_MIN": "t2m_min", "T2MDEW": "t2m_dew",
    "RH2M": "rh2m", "WS2M": "ws2m", "PS": "ps",
    "GWETTOP": "gwet_top", "GWETROOT": "gwet_root", "GWETPROF": "gwet_prof",
    "ALLSKY_SFC_SW_DWN": "solar",
}
VALUE_COLS = ["rain_mm"] + list(DAILY_COLUMNS.values())

DDL = [
    """CREATE TABLE IF NOT EXISTS bd_locations (
        location_id INT NOT NULL PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        division VARCHAR(50),
        kind VARCHAR(20) NOT NULL,
        latitude DOUBLE NOT NULL,
        longitude DOUBLE NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS bd_daily_data (
        location_id INT NOT NULL,
        observation_date DATE NOT NULL,
        rain_mm DOUBLE, imerg_precip DOUBLE, pcorr_precip DOUBLE,
        t2m DOUBLE, t2m_max DOUBLE, t2m_min DOUBLE, t2m_dew DOUBLE,
        rh2m DOUBLE, ws2m DOUBLE, ps DOUBLE,
        gwet_top DOUBLE, gwet_root DOUBLE, gwet_prof DOUBLE, solar DOUBLE,
        data_source VARCHAR(40) NOT NULL,
        PRIMARY KEY (location_id, observation_date)
    )""",
    """CREATE TABLE IF NOT EXISTS bd_flood_events (
        event_id VARCHAR(40) NOT NULL PRIMARY KEY,
        event_name VARCHAR(200) NOT NULL,
        districts TEXT NOT NULL,
        start_date DATE NOT NULL,
        end_date DATE NOT NULL,
        confidence VARCHAR(10),
        flood_type VARCHAR(30),
        notes TEXT,
        source_urls TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS bd_flood_days (
        location_id INT NOT NULL,
        flood_date DATE NOT NULL,
        event_id VARCHAR(40) NOT NULL,
        confidence VARCHAR(10),
        flood_type VARCHAR(30),
        PRIMARY KEY (location_id, flood_date, event_id)
    )""",
    """CREATE TABLE IF NOT EXISTS bd_predictions (
        location_id INT NOT NULL,
        as_of DATE NOT NULL,
        horizon_days INT NOT NULL,
        probability DOUBLE, score DOUBLE,
        risk_level VARCHAR(12),
        rain_1d_mm DOUBLE, rain_3d_mm DOUBLE, rain_7d_mm DOUBLE, soil_wetness_root DOUBLE,
        model_trained_at VARCHAR(30),
        PRIMARY KEY (location_id, as_of, horizon_days)
    )""",
]
VIEW = """CREATE VIEW bd_latest_risk AS
    SELECT l.name AS district, l.division, p.as_of, p.horizon_days, p.risk_level, p.probability,
           p.rain_1d_mm, p.rain_3d_mm, p.rain_7d_mm, p.soil_wetness_root
    FROM bd_predictions p JOIN bd_locations l ON l.location_id = p.location_id
    WHERE p.as_of = (SELECT MAX(as_of) FROM bd_predictions)"""


class MySQLUnavailable(RuntimeError):
    """MySQL cannot be reached or is not configured."""


# ---- connection --------------------------------------------------------------------

def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    env = config.ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("DATABASE_URL="):
                return line.split("=", 1)[1].strip()
    raise MySQLUnavailable("DATABASE_URL was not found in .env")


def parse_url(url: str) -> dict:
    p = urlparse(url)
    return {"host": p.hostname or "localhost", "port": p.port or 3306,
            "user": unquote(p.username or "root"), "password": unquote(p.password or ""),
            "database": p.path.lstrip("/") or "smart_flood_system"}


class Db:
    """Tiny DB-API wrapper so the same code runs on MySQL (real use) and SQLite (tests)."""

    def __init__(self, conn, dialect: str):
        self.conn, self.dialect = conn, dialect
        self.ph = "%s" if dialect == "mysql" else "?"

    def execute(self, sql: str, params=()):
        cur = self.conn.cursor()
        cur.execute(sql, params)
        return cur

    def create_schema(self):
        suffix = " ENGINE=InnoDB DEFAULT CHARSET=utf8mb4" if self.dialect == "mysql" else ""
        for ddl in DDL:
            self.execute(ddl + suffix)
        self.execute("DROP VIEW IF EXISTS bd_latest_risk")
        self.execute(VIEW)
        self.conn.commit()

    def upsert_sql(self, table: str, cols: list, keys: list) -> str:
        values = [c for c in cols if c not in keys]
        head = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join([self.ph] * len(cols))})"
        if self.dialect == "mysql":
            return head + " ON DUPLICATE KEY UPDATE " + ",".join(f"{c}=VALUES({c})" for c in values)
        return head + f" ON CONFLICT({','.join(keys)}) DO UPDATE SET " + ",".join(f"{c}=excluded.{c}" for c in values)

    def upsert(self, table: str, rows: list, keys: list, batch: int = 2000) -> int:
        if not rows:
            return 0
        cols = list(rows[0].keys())
        sql = self.upsert_sql(table, cols, keys)
        data = [tuple(r[c] for c in cols) for r in rows]
        cur = self.conn.cursor()
        for i in range(0, len(data), batch):
            cur.executemany(sql, data[i:i + batch])
            self.conn.commit()
        return len(rows)

    def scalar(self, sql: str):
        return self.execute(sql).fetchone()[0]

    def close(self):
        self.conn.close()


def connect_mysql() -> Db:
    try:
        import pymysql
    except ImportError:
        raise MySQLUnavailable("The 'pymysql' package is missing - run: pip install -r requirements.txt")
    cfg = parse_url(database_url())
    try:
        conn = pymysql.connect(host=cfg["host"], port=cfg["port"], user=cfg["user"],
                               password=cfg["password"], charset="utf8mb4")
    except pymysql.err.OperationalError as exc:
        raise MySQLUnavailable(
            "Could not connect to MySQL. Is MySQL started in XAMPP, and is DATABASE_URL in .env correct "
            f"(user / password / port)?  Details: {exc}")
    cur = conn.cursor()
    cur.execute(f"CREATE DATABASE IF NOT EXISTS `{cfg['database']}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    conn.select_db(cfg["database"])
    return Db(conn, "mysql")


# ---- helpers ----------------------------------------------------------------------

def _clean(v):
    """Python-native value for the database driver (NaN -> NULL)."""
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if hasattr(v, "item"):               # numpy scalar
        v = v.item()
        if isinstance(v, float) and math.isnan(v):
            return None
    if isinstance(v, (pd.Timestamp, date)):
        return v.strftime("%Y-%m-%d")
    return v


def _records(df: pd.DataFrame) -> list:
    return [{k: _clean(v) for k, v in row.items()} for row in df.to_dict(orient="records")]


# ---- exports ----------------------------------------------------------------------

def export_locations(db: Db) -> int:
    d = pd.read_csv(config.DISTRICTS_CSV)
    u = pd.read_csv(config.UPSTREAM_CSV)
    rows = pd.concat([
        pd.DataFrame({"location_id": d["location_id"], "name": d["district"], "division": d["division"],
                      "kind": "district", "latitude": d["latitude"], "longitude": d["longitude"]}),
        pd.DataFrame({"location_id": u["location_id"], "name": u["name"], "division": None,
                      "kind": "upstream", "latitude": u["latitude"], "longitude": u["longitude"]}),
    ])
    return db.upsert("bd_locations", _records(rows.astype(object)), ["location_id"])


def export_daily(db: Db, since: str | None = None, log=print) -> int:
    total = 0
    files = sorted(config.POWER_DIR.glob("[0-9]*.csv"), key=lambda p: int(p.stem))
    if not files:
        log("  no NASA files found in data/power_daily - run:  python -m floodml download")
        return 0
    for f in files:
        df = pd.read_csv(f, index_col="date", parse_dates=True).sort_index()
        if since:
            df = df[df.index >= pd.Timestamp(since)]
        out = pd.DataFrame(index=df.index)
        for src, dst in DAILY_COLUMNS.items():
            out[dst] = df[src] if src in df.columns else float("nan")
        out.insert(0, "rain_mm", out["imerg_precip"].fillna(out["pcorr_precip"]))
        out = out.dropna(how="all")
        if out.empty:
            continue
        out.insert(0, "location_id", int(f.stem))
        out.insert(1, "observation_date", out.index)
        out["data_source"] = "NASA POWER"
        total += db.upsert("bd_daily_data", _records(out.reset_index(drop=True).astype(object)),
                           ["location_id", "observation_date"])
    return total


def export_labels(db: Db) -> tuple:
    from .labels import build_labels

    ev = pd.read_csv(config.EVENTS_CSV)
    n_events = db.upsert("bd_flood_events", _records(ev[[
        "event_id", "event_name", "districts", "start_date", "end_date", "confidence",
        "flood_type", "notes", "source_urls"]].astype(object)), ["event_id"])
    days = build_labels(write=False)
    days = pd.DataFrame({"location_id": days["location_id"], "flood_date": days["date"],
                         "event_id": days["event_id"], "confidence": days["confidence"],
                         "flood_type": days["flood_type"]})
    return n_events, db.upsert("bd_flood_days", _records(days.astype(object)),
                               ["location_id", "flood_date", "event_id"])


def export_predictions(db: Db) -> int:
    import json
    if not config.PRED_JSON.exists():
        return 0
    payload = json.loads(config.PRED_JSON.read_text(encoding="utf-8"))
    trained = payload["meta"].get("model_trained_at")
    rows = [{"location_id": int(r["location_id"]), "as_of": r["as_of"], "horizon_days": int(r["horizon_days"]),
             "probability": r["probability"], "score": r["score"], "risk_level": r["risk_level"],
             "rain_1d_mm": r["rain_1d_mm"], "rain_3d_mm": r["rain_3d_mm"], "rain_7d_mm": r["rain_7d_mm"],
             "soil_wetness_root": r["soil_wetness_root"], "model_trained_at": trained}
            for r in payload["districts"]]
    return db.upsert("bd_predictions", [{k: _clean(v) for k, v in r.items()} for r in rows],
                     ["location_id", "as_of", "horizon_days"])


def export_all(db: Db, only: str = "all", since: str | None = None, log=print) -> dict:
    db.create_schema()
    res = {"locations": export_locations(db)}
    log(f"  bd_locations:    {res['locations']} rows")
    if only in ("all", "daily"):
        res["daily"] = export_daily(db, since, log)
        log(f"  bd_daily_data:   {res['daily']:,} rows written")
    if only in ("all", "labels"):
        res["events"], res["flood_days"] = export_labels(db)
        log(f"  bd_flood_events: {res['events']} rows, bd_flood_days: {res['flood_days']} rows")
    if only in ("all", "predictions"):
        res["predictions"] = export_predictions(db)
        log(f"  bd_predictions:  {res['predictions']} rows")
    return res


def run_export(only: str = "all", since: str | None = None, recent_days: int | None = None, log=print) -> dict:
    if recent_days:
        since = (date.today() - timedelta(days=recent_days)).isoformat()
    db = connect_mysql()
    try:
        log("Exporting to MySQL ...")
        res = export_all(db, only=only, since=since, log=log)
        log("Done. Open phpMyAdmin -> database -> tables starting with bd_ (try the view bd_latest_risk).")
        return res
    finally:
        db.close()
