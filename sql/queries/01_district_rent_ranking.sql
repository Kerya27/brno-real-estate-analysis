-- Question: Which Brno city districts have the highest and lowest asking rent per m2
-- for a typical 2-room flat (2+kk/2+1), and how far is each from the median district?
-- Source: MF ČR rent map, edition 2026-08 (offer prices, not paid rents).
WITH two_room AS (
    SELECT area_name, rent_kc_m2_month, rent_flat_month_kc, yoy_pct
    FROM clean.rent_map
    WHERE area_type = 'city_district' AND size_key = 2
),
med AS (
    SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY rent_kc_m2_month) AS median_rent
    FROM two_room
)
SELECT t.area_name,
       t.rent_kc_m2_month,
       t.rent_flat_month_kc                                   AS rent_55m2_flat_kc,
       t.yoy_pct,
       RANK() OVER (ORDER BY t.rent_kc_m2_month DESC)          AS rank_high_to_low,
       ROUND(((t.rent_kc_m2_month / m.median_rent - 1) * 100)::numeric, 1) AS pct_vs_median
FROM two_room t
CROSS JOIN med m
ORDER BY rank_high_to_low, t.area_name;
