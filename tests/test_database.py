"""Integration tests against PostgreSQL (separate test database).

Skipped automatically when TEST_DATABASE_URL is not reachable, so the unit tests still
run anywhere. CI provides a Postgres 16 service."""

import os

import pandas as pd
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError, OperationalError

from src import load
from src.ingest import read_raw
from src.transform import build_clean

TEST_URL = os.getenv(
    "TEST_DATABASE_URL", "postgresql+psycopg://brno:brno@localhost:5433/brno_re_test"
)


@pytest.fixture(scope="module")
def engine():
    try:
        eng = create_engine(TEST_URL, connect_args={"connect_timeout": 3})
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
    except OperationalError:
        pytest.skip("test database not reachable")
    raw = read_raw()
    clean, _ = build_clean(raw)
    load.load_raw(eng, raw)
    load.load_clean(eng, clean)
    load.build_marts(eng)
    yield eng
    eng.dispose()


def test_layers_exist(engine):
    with engine.connect() as conn:
        schemas = set(
            conn.execute(text("SELECT schema_name FROM information_schema.schemata")).scalars()
        )
    assert {"raw", "clean", "mart"} <= schemas


def test_clean_row_counts(engine):
    with engine.connect() as conn:
        n = conn.execute(text("SELECT COUNT(*) FROM clean.rent_map")).scalar_one()
    assert n == 308


def test_check_constraint_rejects_nonpositive_rent(engine):
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO clean.rent_history VALUES "
                "('brno', DATE '2030-01-01', 2, '2+kk/2+1', -1)"
            )
        )


def test_all_queries_run_and_return_rows(engine):
    results = load.run_queries(engine)
    assert len(results) == 10
    for name, df in results.items():
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0, name


def test_window_query_values(engine):
    r = load.run_queries(engine)
    ranking = r["01_district_rent_ranking"]
    assert ranking.iloc[0]["area_name"] == "Brno-jih"  # highest 2-room rent per m2
    okres = r["05_okres_price_growth"].set_index("area_name")
    assert okres.loc["Brno-město", "price_rank_2025"] == 1
