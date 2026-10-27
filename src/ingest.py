"""Raw layer: read the source snapshots in data/raw exactly as published.

The pipeline always runs from the committed snapshots so results are reproducible.
`refresh_rent_map()` can re-download the one source that has a stable machine-readable
URL (MF ČR rent map CSV republished by Brno pod lupou, CC BY 4.0); it writes a new
dated file instead of overwriting the snapshot.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from src.config import RAW_DIR

RAW_FILES = {
    "rent_map": "mf_rent_map_brno_2026-08.csv",
    "rent_history": "mf_rent_history_city_aggregates.csv",
    "rent_sizes": "mf_rent_size_categories.csv",
    "okres_prices": "csu_apartment_prices_okres_2023_2025.csv",
    "price_index": "csu_apartment_price_index_2015_100.csv",
    "wages": "csu_wages_jmk.csv",
    "mortgage_rates": "cba_mortgage_rates.csv",
}

RENT_MAP_URL = "https://www.brnopodlupou.cz/data/cenova-mapa-najmu.csv"


def read_raw(raw_dir: Path = RAW_DIR) -> dict[str, pd.DataFrame]:
    """Read every raw file as text-faithful as possible (no type coercion beyond CSV)."""
    frames = {}
    for name, filename in RAW_FILES.items():
        path = raw_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Missing raw file {path}; see DATA_SOURCES.md")
        frames[name] = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])
    return frames


def refresh_rent_map(raw_dir: Path = RAW_DIR, timeout: int = 30) -> Path:
    """Download the latest MF ČR rent map CSV to data/raw/mf_rent_map_brno_latest_<date>.csv."""
    import requests

    response = requests.get(RENT_MAP_URL, timeout=timeout)
    response.raise_for_status()
    target = raw_dir / f"mf_rent_map_brno_latest_{date.today().isoformat()}.csv"
    target.write_bytes(response.content)
    return target


if __name__ == "__main__":
    print(f"Saved {refresh_rent_map()}")
