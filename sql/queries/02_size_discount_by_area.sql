-- Question: How much cheaper per m2 are bigger flats than 1-room flats in each
-- cadastral area? (A raw, model-free version of the regression's size effect.)
WITH pivot AS (
    SELECT area_name,
           MAX(rent_kc_m2_month) FILTER (WHERE size_key = 1) AS r1,
           MAX(rent_kc_m2_month) FILTER (WHERE size_key = 2) AS r2,
           MAX(rent_kc_m2_month) FILTER (WHERE size_key = 3) AS r3,
           MAX(rent_kc_m2_month) FILTER (WHERE size_key = 4) AS r4
    FROM clean.rent_map
    WHERE area_type = 'cadastral_area'
    GROUP BY area_name
)
SELECT area_name, r1, r2, r3, r4,
       ROUND(((r2 / r1 - 1) * 100)::numeric, 1) AS pct_2room_vs_1room,
       ROUND(((r3 / r1 - 1) * 100)::numeric, 1) AS pct_3room_vs_1room,
       ROUND(((r4 / r1 - 1) * 100)::numeric, 1) AS pct_4room_vs_1room
FROM pivot
ORDER BY pct_3room_vs_1room;
