"""Clean layer: typed, normalized, deduplicated tables with every decision logged."""

from __future__ import annotations

import pandas as pd

from src.cleaning import (
    SIZE_LABEL,
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
    period_to_date,
    standardize_size_category,
)

AREA_TYPE = {"katastralni_uzemi": "cadastral_area", "mestska_cast": "city_district"}


def clean_rent_map(raw: pd.DataFrame, sizes: pd.DataFrame, log: CleaningLog) -> pd.DataFrame:
    ds = "rent_map"
    log.record(ds, "read_raw", len(raw), len(raw), "raw rows")
    df = pd.DataFrame(
        {
            "area_type": raw["uzemi_typ"].map(AREA_TYPE),
            "ruian_code": pd.to_numeric(raw["kod_ruian"], errors="coerce"),
            "area_name": raw["nazev"].map(normalize_district_name),
            "size_key": raw["velikost_bytu"].map(standardize_size_category),
            "rent_kc_m2_month": raw["median_kc_m2_mesic"].map(parse_czech_number),
            "yoy_pct": raw["zmena_rok_pct"].map(parse_czech_number),
            "period": period_to_date(raw["obdobi"]),
        }
    )
    df = drop_missing(
        df, ["area_type", "ruian_code", "area_name", "size_key", "rent_kc_m2_month"], log, ds
    )
    df = drop_nonpositive(df, "rent_kc_m2_month", log, ds)
    df = drop_duplicates_logged(df, ["area_type", "ruian_code", "size_key"], log, ds)
    df["ruian_code"] = df["ruian_code"].astype(int)
    df["size_key"] = df["size_key"].astype(int)
    df["size_label"] = df["size_key"].map(SIZE_LABEL)
    area = sizes.assign(
        size_key=sizes["size_key"].astype(int), model_area_m2=sizes["model_area_m2"].astype(float)
    )
    df = df.merge(area[["size_key", "model_area_m2"]], on="size_key", how="left")
    # yoy is needed to back out the 2025-08 rent; if it is missing that value stays NaN
    df["rent_kc_m2_month_prev_year"] = back_out_previous(
        df["rent_kc_m2_month"], df["yoy_pct"]
    ).round(1)
    df["rent_kc_m2_year"] = monthly_to_annual(df["rent_kc_m2_month"])
    df["rent_flat_month_kc"] = (df["rent_kc_m2_month"] * df["model_area_m2"]).round(0)
    flagged = []
    for _, part in df.groupby("area_type"):
        flagged.append(flag_outliers(part, "rent_kc_m2_month", group_col="size_key"))
    df = pd.concat(flagged).sort_values(["area_type", "area_name", "size_key"])
    n_out = int(df["is_outlier"].sum())
    log.record(
        ds,
        "flag_outliers",
        len(df),
        len(df),
        f"{n_out} rows flagged (|modified z| > 3.5 on log rent within size); kept",
    )
    return df.reset_index(drop=True)


def clean_rent_history(raw: pd.DataFrame, log: CleaningLog) -> pd.DataFrame:
    ds = "rent_history"
    log.record(ds, "read_raw", len(raw), len(raw), "raw rows")
    df = pd.DataFrame(
        {
            "aggregate": raw["aggregate"].str.strip().str.lower(),
            "period": period_to_date(raw["period"]),
            "size_key": pd.to_numeric(raw["size_key"], errors="coerce"),
            "rent_kc_m2_month": raw["median_kc_m2_mesic"].map(parse_czech_number),
        }
    )
    df = drop_missing(df, ["size_key", "rent_kc_m2_month"], log, ds)
    df = drop_nonpositive(df, "rent_kc_m2_month", log, ds)
    df = drop_duplicates_logged(df, ["aggregate", "period", "size_key"], log, ds)
    df["size_key"] = df["size_key"].astype(int)
    df["size_label"] = df["size_key"].map(SIZE_LABEL)
    return df.sort_values(["aggregate", "size_key", "period"]).reset_index(drop=True)


def clean_okres_prices(raw: pd.DataFrame, log: CleaningLog) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (areas, prices_long). areas = one row per territory with transaction
    count and average flat size; prices_long = territory x year price per m2."""
    ds = "okres_prices"
    log.record(ds, "read_raw", len(raw), len(raw), "raw rows")
    raw = raw.assign(uzemi=raw["uzemi"].map(normalize_district_name))
    raw = drop_duplicates_logged(raw, ["uzemi"], log, ds)
    areas = pd.DataFrame(
        {
            "area_name": raw["uzemi"],
            "area_level": raw["uzemi_typ"].str.strip(),
            "region": raw["kraj"].map(normalize_district_name),
            "transactions_2023_2025": raw["pocet_prevodu_2023_2025"].map(parse_czech_number),
            "avg_flat_m2": raw["prumerna_velikost_bytu_m2"].map(parse_czech_number),
            "price_kc_m2_2023_2025": raw["cena_kc_m2_2023_2025"].map(parse_czech_number),
        }
    )
    long = raw.melt(
        id_vars=["uzemi"],
        value_vars=["cena_kc_m2_2023", "cena_kc_m2_2024", "cena_kc_m2_2025"],
        var_name="col",
        value_name="price",
    )
    prices = pd.DataFrame(
        {
            "area_name": long["uzemi"],
            "year": long["col"].str[-4:].astype(int),
            "price_kc_m2": long["price"].map(parse_czech_number),
        }
    )
    prices = drop_missing(prices, ["price_kc_m2"], log, ds + "_long")
    prices = drop_nonpositive(prices, "price_kc_m2", log, ds + "_long")
    return areas.reset_index(drop=True), prices.sort_values(["area_name", "year"]).reset_index(
        drop=True
    )


def clean_price_index(raw: pd.DataFrame, log: CleaningLog) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (quarterly_long, annual). Checks annual average == mean of quarters."""
    ds = "price_index"
    log.record(ds, "read_raw", len(raw), len(raw), "raw rows")
    df = raw.copy()
    for col in ["q1", "q2", "q3", "q4", "prumer_roku"]:
        df[col] = df[col].map(parse_czech_number)
    df["rok"] = df["rok"].astype(int)
    df["uzemi"] = df["uzemi"].map(normalize_district_name)
    df = drop_duplicates_logged(df, ["uzemi", "rok"], log, ds)
    bad = check_index_consistency(df)
    log.record(
        ds,
        "check_annual_vs_quarters",
        len(df),
        len(df),
        f"{len(bad)} rows where annual avg differs from mean of quarters by > 0.15",
    )
    annual = df.rename(
        columns={"uzemi": "area_name", "rok": "year", "prumer_roku": "index_2015_100"}
    )[["area_name", "year", "index_2015_100"]]
    q = df.melt(
        id_vars=["uzemi", "rok"],
        value_vars=["q1", "q2", "q3", "q4"],
        var_name="quarter",
        value_name="index_2015_100",
    )
    q["quarter"] = q["quarter"].str[1].astype(int)
    q = q.rename(columns={"uzemi": "area_name", "rok": "year"})
    q = drop_missing(q, ["index_2015_100"], log, ds + "_quarterly")
    q["period"] = pd.PeriodIndex.from_fields(
        year=q["year"], quarter=q["quarter"], freq="Q"
    ).to_timestamp()
    return q.sort_values(["area_name", "period"]).reset_index(drop=True), annual


def clean_wages(raw: pd.DataFrame, log: CleaningLog) -> pd.DataFrame:
    ds = "wages"
    log.record(ds, "read_raw", len(raw), len(raw), "raw rows")
    df = pd.DataFrame(
        {
            "region": raw["uzemi"].map(normalize_district_name),
            "period": raw["obdobi"].str.strip(),
            "avg_gross_wage_kc": raw["prumerna_hruba_mzda_kc"].map(parse_czech_number),
            "note": raw["poznamka"],
        }
    )
    df = drop_missing(df, ["avg_gross_wage_kc"], log, ds)
    return drop_duplicates_logged(df, ["region", "period"], log, ds).reset_index(drop=True)


def clean_mortgage_rates(raw: pd.DataFrame, log: CleaningLog) -> pd.DataFrame:
    ds = "mortgage_rates"
    log.record(ds, "read_raw", len(raw), len(raw), "raw rows")
    df = pd.DataFrame(
        {
            "period": raw["obdobi"].str.strip(),
            "kind": raw["typ"].str.strip(),
            "rate_pct": raw["sazba_pct"].map(parse_czech_number),
        }
    )
    df = drop_missing(df, ["rate_pct"], log, ds)
    return drop_duplicates_logged(df, ["period", "kind"], log, ds).reset_index(drop=True)


def build_clean(raw: dict[str, pd.DataFrame]) -> tuple[dict[str, pd.DataFrame], CleaningLog]:
    log = CleaningLog()
    areas, prices = clean_okres_prices(raw["okres_prices"], log)
    idx_q, idx_a = clean_price_index(raw["price_index"], log)
    clean = {
        "rent_map": clean_rent_map(raw["rent_map"], raw["rent_sizes"], log),
        "rent_history": clean_rent_history(raw["rent_history"], log),
        "okres_areas": areas,
        "okres_prices": prices,
        "price_index_q": idx_q,
        "price_index_a": idx_a,
        "wages": clean_wages(raw["wages"], log),
        "mortgage_rates": clean_mortgage_rates(raw["mortgage_rates"], log),
    }
    return clean, log
