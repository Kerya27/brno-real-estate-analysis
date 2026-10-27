-- Question: What gross rental yield and payback period would a landlord get in each
-- district if they paid the Brno-město average 2025 transaction price?
-- Rent is matched to 2025 (edition 2025-08, backed out from the yoy change).
-- District sale prices are NOT available, so yields differ only through rent.
WITH price AS (
    SELECT price_kc_m2 FROM clean.okres_prices
    WHERE area_name = 'Brno-město' AND year = 2025
)
SELECT r.area_name, r.size_label,
       r.rent_kc_m2_month_prev_year                                    AS rent_2025_kc_m2,
       p.price_kc_m2                                                   AS price_2025_kc_m2,
       ROUND((r.rent_kc_m2_month_prev_year * 12 / p.price_kc_m2 * 100)::numeric, 2)
           AS gross_yield_pct,
       ROUND((p.price_kc_m2 / (r.rent_kc_m2_month_prev_year * 12))::numeric, 1)
           AS payback_years
FROM clean.rent_map r
CROSS JOIN price p
WHERE r.area_type = 'city_district'
ORDER BY r.size_key, gross_yield_pct DESC;
