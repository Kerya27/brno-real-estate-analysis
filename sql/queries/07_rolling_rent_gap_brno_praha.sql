-- Question: Is Brno catching up with Prague? Ratio of Brno to Prague asking rent per m2
-- (2-room flats) and its rolling 4-edition (1-year) average.
WITH pair AS (
    SELECT period,
           MAX(rent_kc_m2_month) FILTER (WHERE aggregate = 'brno')  AS brno,
           MAX(rent_kc_m2_month) FILTER (WHERE aggregate = 'praha') AS praha
    FROM clean.rent_history
    WHERE size_key = 2
    GROUP BY period
)
SELECT period, brno, praha,
       ROUND((brno / praha * 100)::numeric, 1) AS brno_pct_of_praha,
       ROUND((AVG(brno / praha) OVER (ORDER BY period
                                      ROWS BETWEEN 3 PRECEDING AND CURRENT ROW) * 100)::numeric,
             1) AS rolling_1y_pct_of_praha
FROM pair
ORDER BY period;
