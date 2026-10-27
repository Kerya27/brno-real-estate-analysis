"""Unit tests for cleaning functions. All frames here are small SYNTHETIC examples."""

import numpy as np
import pandas as pd
import pytest

from src.cleaning import (
    CleaningLog,
    back_out_previous,
    check_index_consistency,
    drop_duplicates_logged,
    drop_missing,
    drop_nonpositive,
    flag_outliers,
    monthly_to_annual,
    normalize_district_name,
    parse_czech_number,
    pct_to_fraction,
    period_to_date,
    robust_zscore,
    standardize_size_category,
)

# ------------------------------------------------------------- district names


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Brno-střed", "Brno-střed"),
        ("  Brno – střed ", "Brno-střed"),  # en dash with spaces
        ("Brno -  sever", "Brno-sever"),
        ("brno stred", "Brno-střed"),  # accent-less alias
        ("BRNO-MESTO", "Brno-město"),
        ("Královo   Pole", "Královo Pole"),  # repeated spaces
        ("Kálovo", "Kálovo"),  # decomposed accent -> NFC
    ],
)
def test_normalize_district_name(raw, expected):
    assert normalize_district_name(raw) == expected


@pytest.mark.parametrize("raw", [None, np.nan, "", "   "])
def test_normalize_district_name_missing(raw):
    assert normalize_district_name(raw) is None


# ------------------------------------------------------------- size categories


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("1+kk / 1+1", 1),
        ("2+kk / 2+1", 2),
        ("4 a více", 4),
        ("3+1", 3),
        ("5+kk", 4),  # 5+ rooms fold into the "4 and more" bucket
        ("garsoniéra", None),
        (None, None),
    ],
)
def test_standardize_size_category(raw, expected):
    assert standardize_size_category(raw) == expected


# ------------------------------------------------------------- numbers and units


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("89 421", 89421.0),
        ("89 421", 89421.0),  # non-breaking space thousands separator
        ("4,58", 4.58),
        ("1 234,5 Kč", 1234.5),
        ("x", None),  # ČSÚ suppressed cell
        ("", None),
        (310, 310.0),
        ("abc", None),
    ],
)
def test_parse_czech_number(raw, expected):
    assert parse_czech_number(raw) == expected


def test_unit_conversions():
    assert monthly_to_annual(300) == 3600
    assert pct_to_fraction(4.58) == pytest.approx(0.0458)
    s = period_to_date(pd.Series(["2026-08", "2019-02"]))
    assert s.iloc[0] == pd.Timestamp("2026-08-01")
    assert s.iloc[1] == pd.Timestamp("2019-02-01")


def test_back_out_previous_year_value():
    # 110 after +10 % growth -> 100 a year earlier
    prev = back_out_previous(pd.Series([110.0, 100.0]), pd.Series([10.0, -20.0]))
    assert prev.tolist() == pytest.approx([100.0, 125.0])


# ------------------------------------------------------------- missing / duplicates


def test_drop_missing_logs_removed_rows():
    log = CleaningLog()
    df = pd.DataFrame({"area": ["A", "B", None], "rent": [300, np.nan, 280]})
    out = drop_missing(df, ["area", "rent"], log, "synthetic")
    assert out["area"].tolist() == ["A"]
    entry = log.to_frame().iloc[0]
    assert entry["rows_before"] == 3 and entry["rows_removed"] == 2


def test_drop_duplicates_keeps_first():
    log = CleaningLog()
    df = pd.DataFrame({"k": [1, 1, 2], "size": [2, 2, 2], "rent": [300, 999, 280]})
    out = drop_duplicates_logged(df, ["k", "size"], log, "synthetic")
    assert out["rent"].tolist() == [300, 280]
    assert log.to_frame()["rows_removed"].iloc[0] == 1


def test_drop_nonpositive():
    log = CleaningLog()
    df = pd.DataFrame({"price": [100.0, 0.0, -5.0, 50.0]})
    out = drop_nonpositive(df, "price", log, "synthetic")
    assert out["price"].tolist() == [100.0, 50.0]


# ------------------------------------------------------------- outliers


def test_robust_zscore_handles_constant_series():
    z = robust_zscore(pd.Series([5.0, 5.0, 5.0]))
    assert (z == 0).all()


def test_flag_outliers_flags_extreme_value_only():
    rng = np.random.default_rng(42)  # fixed seed: synthetic data is reproducible
    values = list(300 + rng.normal(0, 5, size=30)) + [900.0]
    df = pd.DataFrame({"rent": values, "size": 1})
    out = flag_outliers(df, "rent", group_col="size")
    assert out["is_outlier"].sum() == 1
    assert bool(out["is_outlier"].iloc[-1])
    assert len(out) == len(df)  # flagged, not dropped


def test_flag_outliers_is_computed_within_groups():
    # group 2 is uniformly cheaper; without grouping its rows would look like outliers
    df = pd.DataFrame(
        {
            "rent": [400, 402, 398, 401, 399, 200, 201, 199, 202, 198],
            "size": [1] * 5 + [4] * 5,
        }
    )
    out = flag_outliers(df, "rent", group_col="size")
    assert not out["is_outlier"].any()


# ------------------------------------------------------------- index check


def test_check_index_consistency_finds_bad_row():
    df = pd.DataFrame(
        {
            "q1": [98.0, 100.0],
            "q2": [99.3, 100.0],
            "q3": [101.0, 100.0],
            "q4": [101.7, 100.0],
            "prumer_roku": [100.0, 105.0],  # second row is inconsistent
        }
    )
    bad = check_index_consistency(df)
    assert bad.index.tolist() == [1]
