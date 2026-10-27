-- Question: What is the compound annual growth rate of asking rents from the first
-- (2019-02) to the latest (2026-08) edition, per city aggregate and flat size?
WITH ends AS (
    SELECT DISTINCT aggregate, size_key, size_label,
           FIRST_VALUE(rent_kc_m2_month) OVER w AS first_rent,
           LAST_VALUE(rent_kc_m2_month)  OVER w AS last_rent,
           FIRST_VALUE(period) OVER w AS first_period,
           LAST_VALUE(period)  OVER w AS last_period
    FROM clean.rent_history
    WINDOW w AS (PARTITION BY aggregate, size_key ORDER BY period
                 ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING)
)
SELECT aggregate, size_label, first_period, last_period, first_rent, last_rent,
       ROUND(((POWER(last_rent / first_rent,
                     365.25 / (last_period - first_period)) - 1) * 100)::numeric, 2)
           AS cagr_pct
FROM ends
ORDER BY size_key, cagr_pct DESC;
