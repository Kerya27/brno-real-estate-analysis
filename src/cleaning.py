"""Cleaning functions. Each one is pure (DataFrame in, DataFrame out) and every step
that can drop rows reports how many it removed through a CleaningLog."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# ---------------------------------------------------------------- cleaning log


@dataclass
class CleaningLog:
    """Collects one entry per cleaning step: dataset, step, rows before/after, reason."""

    entries: list[dict] = field(default_factory=list)

    def record(self, dataset: str, step: str, before: int, after: int, reason: str) -> None:
        self.entries.append(
            {
                "dataset": dataset,
                "step": step,
                "rows_before": before,
                "rows_after": after,
                "rows_removed": before - after,
                "reason": reason,
            }
        )

    def to_frame(self) -> pd.DataFrame:
        cols = ["dataset", "step", "rows_before", "rows_after", "rows_removed", "reason"]
        return pd.DataFrame(self.entries, columns=cols)


# ---------------------------------------------------------------- text / names

_DASH_RE = re.compile(r"\s*[-‐‑‒–—]\s*")
_SPACE_RE = re.compile(r"\s+")

# Known spelling variants seen in Czech sources -> canonical RÚIAN name.
DISTRICT_ALIASES = {
    "brno stred": "Brno-střed",
    "brno-stred": "Brno-střed",
    "brno mesto": "Brno-město",
    "brno-mesto": "Brno-město",
    "brno venkov": "Brno-venkov",
    "brno-venkov": "Brno-venkov",
    "kralovo pole": "Královo Pole",
    "mesto brno": "Město Brno",
}


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def normalize_district_name(name: object) -> str | None:
    """Canonical form of a district name.

    - Unicode NFC, trimmed, single spaces
    - any dash variant with optional spaces ("Brno – střed") becomes "-"
    - an all-lowercase / accent-less alias ("brno stred") maps to the RÚIAN spelling
    Missing values stay None.
    """
    if name is None or (isinstance(name, float) and np.isnan(name)):
        return None
    text = unicodedata.normalize("NFC", str(name)).strip()
    if not text:
        return None
    text = _DASH_RE.sub("-", text)
    text = _SPACE_RE.sub(" ", text)
    key = strip_accents(text).lower()
    if key in DISTRICT_ALIASES:
        return DISTRICT_ALIASES[key]
    return text


SIZE_MAP = {
    "1+kk / 1+1": 1,
    "2+kk / 2+1": 2,
    "3+kk / 3+1": 3,
    "4 a více": 4,
}
SIZE_LABEL = {1: "1+kk/1+1", 2: "2+kk/2+1", 3: "3+kk/3+1", 4: "4+ rooms"}


def standardize_size_category(value: object) -> int | None:
    """Map the MF ČR size label (or a variant like '2+1', '3kk', '4+') to 1..4."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    text = _SPACE_RE.sub(" ", str(value).strip())
    if text in SIZE_MAP:
        return SIZE_MAP[text]
    match = re.match(r"^\s*(\d)", text)
    if not match:
        return None
    rooms = int(match.group(1))
    if rooms < 1:
        return None
    return min(rooms, 4)


# ---------------------------------------------------------------- numbers / units


def parse_czech_number(value: object) -> float | None:
    """'89 421' -> 89421.0, '4,58' -> 4.58, '1 234,5 Kč' -> 1234.5, 'x' / '' -> None.

    ČSÚ tables use a (non-breaking) space as thousands separator, a decimal comma
    and 'x' for suppressed cells.
    """
    if value is None:
        return None
    if isinstance(value, int | float | np.integer | np.floating):
        return None if pd.isna(value) else float(value)
    text = str(value).replace(" ", " ").replace(" ", " ").strip()
    text = re.sub(r"(Kč|%|m2|m²)$", "", text).strip()
    if text in {"", "x", "X", "-", "."}:
        return None
    text = text.replace(" ", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def monthly_to_annual(kc_per_m2_month: pd.Series | float) -> pd.Series | float:
    """Rent unit conversion: Kč/m2/month -> Kč/m2/year."""
    return kc_per_m2_month * 12


def pct_to_fraction(pct: pd.Series | float) -> pd.Series | float:
    return pct / 100.0


def period_to_date(period: pd.Series) -> pd.Series:
    """'2026-08' (MF edition month) -> first day of that month as datetime."""
    return pd.to_datetime(period.astype(str) + "-01", format="%Y-%m-%d")


def back_out_previous(value: pd.Series, yoy_pct: pd.Series) -> pd.Series:
    """Value one year earlier from the current value and its yoy % change:
    prev = value / (1 + yoy/100). Used to get 2025-08 district rents."""
    return value / (1 + yoy_pct / 100.0)


# ---------------------------------------------------------------- rows


def drop_missing(
    df: pd.DataFrame, columns: list[str], log: CleaningLog, dataset: str
) -> pd.DataFrame:
    """Drop rows where any of `columns` is missing. Imputation is NOT used: a
    missing price or rent has no defensible substitute in this data."""
    before = len(df)
    out = df.dropna(subset=columns).copy()
    log.record(dataset, "drop_missing", before, len(out), f"missing value in {columns}")
    return out


def drop_duplicates_logged(
    df: pd.DataFrame, key: list[str], log: CleaningLog, dataset: str
) -> pd.DataFrame:
    """Remove duplicate keys, keeping the first occurrence."""
    before = len(df)
    out = df.drop_duplicates(subset=key, keep="first").copy()
    log.record(dataset, "drop_duplicates", before, len(out), f"duplicate key {key}")
    return out


def robust_zscore(values: pd.Series) -> pd.Series:
    """Modified z-score (Iglewicz & Hoaglin): 0.6745 * (x - median) / MAD.
    Robust to the outliers it is meant to find. MAD == 0 gives 0."""
    x = values.astype(float)
    med = x.median()
    mad = (x - med).abs().median()
    if mad == 0 or np.isnan(mad):
        return pd.Series(0.0, index=values.index)
    return 0.6745 * (x - med) / mad


def flag_outliers(
    df: pd.DataFrame, value_col: str, group_col: str | None = None, threshold: float = 3.5
) -> pd.DataFrame:
    """Add `is_outlier` using |modified z| > threshold (default 3.5) on log(value),
    computed within `group_col` if given. Rows are FLAGGED, not dropped; the
    regression is re-run without them as a robustness check."""
    out = df.copy()
    logged = np.log(out[value_col].astype(float))
    if group_col:
        z = logged.groupby(out[group_col]).transform(robust_zscore)
    else:
        z = robust_zscore(logged)
    out["robust_z"] = z.round(3)
    out["is_outlier"] = z.abs() > threshold
    return out


def drop_nonpositive(df: pd.DataFrame, column: str, log: CleaningLog, dataset: str) -> pd.DataFrame:
    """Prices and rents must be > 0; anything else is a data error."""
    before = len(df)
    out = df[df[column] > 0].copy()
    log.record(dataset, "drop_nonpositive", before, len(out), f"{column} <= 0")
    return out


def check_index_consistency(df: pd.DataFrame, tolerance: float = 0.15) -> pd.DataFrame:
    """ČSÚ index table: the published annual average should equal the mean of the
    four quarters (up to rounding). Returns rows that break the rule."""
    quarters = df[["q1", "q2", "q3", "q4"]].mean(axis=1)
    bad = (quarters - df["prumer_roku"]).abs() > tolerance
    return df.loc[bad]
