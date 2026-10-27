"""Load layers into PostgreSQL and run SQL files."""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import OperationalError

from src.config import QUERIES_DIR, SQL_DIR, database_url


def get_engine(url: str | None = None, retries: int = 20, wait_s: float = 1.5) -> Engine:
    """Create an engine and wait until the database accepts connections
    (the pipeline container can start a moment before Postgres is ready)."""
    engine = create_engine(url or database_url(), pool_pre_ping=True)
    for attempt in range(retries):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return engine
        except OperationalError:
            if attempt == retries - 1:
                raise
            time.sleep(wait_s)
    return engine


def run_sql_file(engine: Engine, path: Path) -> None:
    with engine.begin() as conn:
        conn.exec_driver_sql(path.read_text(encoding="utf-8"))


def load_raw(engine: Engine, raw: dict[str, pd.DataFrame]) -> None:
    """Raw layer: source files as text columns, replaced on every run."""
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE SCHEMA IF NOT EXISTS raw")
        for name, df in raw.items():
            df.to_sql(name, conn, schema="raw", if_exists="replace", index=False)


def load_clean(engine: Engine, clean: dict[str, pd.DataFrame]) -> None:
    """Clean layer: tables are created by sql/schema.sql (types + constraints),
    then filled in dependency order inside one transaction."""
    run_sql_file(engine, SQL_DIR / "schema.sql")
    order = [
        "okres_areas",
        "okres_prices",
        "rent_map",
        "rent_history",
        "price_index_q",
        "price_index_a",
        "wages",
        "mortgage_rates",
    ]
    with engine.begin() as conn:
        for name in order:
            clean[name].to_sql(name, conn, schema="clean", if_exists="append", index=False)


def build_marts(engine: Engine) -> None:
    run_sql_file(engine, SQL_DIR / "marts.sql")


def write_mart(engine: Engine, name: str, df: pd.DataFrame) -> None:
    with engine.begin() as conn:
        df.to_sql(name, conn, schema="mart", if_exists="replace", index=False)


def run_queries(engine: Engine, queries_dir: Path = QUERIES_DIR) -> dict[str, pd.DataFrame]:
    results = {}
    with engine.connect() as conn:
        for path in sorted(queries_dir.glob("*.sql")):
            results[path.stem] = pd.read_sql(text(path.read_text(encoding="utf-8")), conn)
    return results


def read_table(engine: Engine, qualified_name: str) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(text(f"SELECT * FROM {qualified_name}"), conn)
