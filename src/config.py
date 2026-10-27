"""Project paths, database URL and analysis assumptions (one place to change them)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
SQL_DIR = ROOT / "sql"
QUERIES_DIR = SQL_DIR / "queries"
REPORTS_DIR = ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"

DEFAULT_DB_URL = "postgresql+psycopg://brno:brno@localhost:5433/brno_re"

# Fixed seed for anything random (only synthetic test data and bootstrap use it).
RANDOM_SEED = 42


def database_url() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_DB_URL)


@dataclass(frozen=True)
class Assumptions:
    """Assumptions for rent-vs-buy and affordability. Every number has a source in
    DATA_SOURCES.md or is an explicit, documented choice."""

    # ČSÚ: average transaction price of apartments, okres Brno-město, 2025 (Kč/m2)
    price_year: int = 2025
    # ČSÚ: average floor area of transacted apartments in Brno-město 2023-2025 (m2)
    avg_flat_m2: float = 63.0
    # Mortgage: loan-to-value 80 % (ČNB recommended max LTV for most borrowers), 30 years
    ltv: float = 0.80
    term_years: int = 30
    # ČBA Hypomonitor average rate on new mortgages: 2025 average and latest month
    rate_2025_avg_pct: float = 4.58
    rate_latest_pct: float = 5.10
    rate_latest_period: str = "2026-09"
    # Rent offer period matched to the 2025 price year (derived via the yoy change)
    rent_match_period: str = "2025-08"


ASSUMPTIONS = Assumptions()
