-- Three layers, three schemas:
--   raw   = source files loaded as text, untouched (created by the loader with pandas)
--   clean = typed, normalized, deduplicated tables with constraints (defined here)
--   mart  = aggregated tables built from clean (sql/marts.sql) + model outputs

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS clean;
CREATE SCHEMA IF NOT EXISTS mart;

DROP TABLE IF EXISTS clean.rent_map CASCADE;
CREATE TABLE clean.rent_map (
    area_type                  VARCHAR(20)   NOT NULL
        CHECK (area_type IN ('cadastral_area', 'city_district')),
    ruian_code                 INTEGER       NOT NULL,
    area_name                  VARCHAR(80)   NOT NULL,
    size_key                   SMALLINT      NOT NULL CHECK (size_key BETWEEN 1 AND 4),
    size_label                 VARCHAR(20)   NOT NULL,
    model_area_m2              NUMERIC(6, 1) NOT NULL,
    rent_kc_m2_month           NUMERIC(8, 1) NOT NULL CHECK (rent_kc_m2_month > 0),
    yoy_pct                    NUMERIC(6, 1),
    period                     DATE          NOT NULL,
    rent_kc_m2_month_prev_year NUMERIC(8, 1),
    rent_kc_m2_year            NUMERIC(10, 1) NOT NULL,
    rent_flat_month_kc         NUMERIC(10, 0) NOT NULL,
    robust_z                   NUMERIC(8, 3),
    is_outlier                 BOOLEAN       NOT NULL,
    PRIMARY KEY (area_type, ruian_code, size_key)
);

DROP TABLE IF EXISTS clean.rent_history CASCADE;
CREATE TABLE clean.rent_history (
    aggregate        VARCHAR(10)  NOT NULL CHECK (aggregate IN ('brno', 'praha', 'cr')),
    period           DATE         NOT NULL,
    size_key         SMALLINT     NOT NULL CHECK (size_key BETWEEN 1 AND 4),
    size_label       VARCHAR(20)  NOT NULL,
    rent_kc_m2_month NUMERIC(8, 1) NOT NULL CHECK (rent_kc_m2_month > 0),
    PRIMARY KEY (aggregate, period, size_key)
);

DROP TABLE IF EXISTS clean.okres_areas CASCADE;
CREATE TABLE clean.okres_areas (
    area_name              VARCHAR(80) PRIMARY KEY,
    area_level             VARCHAR(10) NOT NULL CHECK (area_level IN ('stat', 'kraj', 'okres')),
    region                 VARCHAR(80),
    transactions_2023_2025 INTEGER,
    avg_flat_m2            NUMERIC(6, 1),
    price_kc_m2_2023_2025  NUMERIC(10, 0)
);

DROP TABLE IF EXISTS clean.okres_prices CASCADE;
CREATE TABLE clean.okres_prices (
    area_name   VARCHAR(80) NOT NULL REFERENCES clean.okres_areas (area_name),
    year        SMALLINT    NOT NULL,
    price_kc_m2 NUMERIC(10, 0) NOT NULL CHECK (price_kc_m2 > 0),
    PRIMARY KEY (area_name, year)
);

DROP TABLE IF EXISTS clean.price_index_q CASCADE;
CREATE TABLE clean.price_index_q (
    area_name      VARCHAR(80) NOT NULL,
    year           SMALLINT    NOT NULL,
    quarter        SMALLINT    NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    index_2015_100 NUMERIC(7, 1) NOT NULL,
    period         DATE        NOT NULL,
    PRIMARY KEY (area_name, year, quarter)
);

DROP TABLE IF EXISTS clean.price_index_a CASCADE;
CREATE TABLE clean.price_index_a (
    area_name      VARCHAR(80) NOT NULL,
    year           SMALLINT    NOT NULL,
    index_2015_100 NUMERIC(7, 1) NOT NULL,
    PRIMARY KEY (area_name, year)
);

DROP TABLE IF EXISTS clean.wages CASCADE;
CREATE TABLE clean.wages (
    region            VARCHAR(80) NOT NULL,
    period            VARCHAR(10) NOT NULL,
    avg_gross_wage_kc NUMERIC(10, 0) NOT NULL,
    note              TEXT,
    PRIMARY KEY (region, period)
);

DROP TABLE IF EXISTS clean.mortgage_rates CASCADE;
CREATE TABLE clean.mortgage_rates (
    period   VARCHAR(10)  NOT NULL,
    kind     VARCHAR(20)  NOT NULL CHECK (kind IN ('month', 'annual_average')),
    rate_pct NUMERIC(5, 2) NOT NULL,
    PRIMARY KEY (period, kind)
);
