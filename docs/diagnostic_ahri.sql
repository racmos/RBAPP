-- =============================================================================
-- Diagnostic: Ahri Alluring price display issue (REQ-3)
-- =============================================================================
-- Purpose: Investigate why Ahri Alluring (rare) shows no price in the
--          collection view. Run on production PostgreSQL.
--
-- Expected flow:
--   1. rbcards has Ahri Alluring with rbcar_rarity = 'Rare'
--   2. rbcm_product_card_map has a mapping for that (rbset_id, rbcar_id)
--   3. rbcm_price has avg7_foil for the mapped idProduct on the latest date
--   4. _resolve_price picks avg7_foil for Rare/Epic (see collection.py:127)
-- =============================================================================

-- Step 1: Find Ahri Alluring in rbcards
SELECT
    rbcar_rbset_id,
    rbcar_id,
    rbcar_name,
    rbcar_rarity,
    rbcar_type,
    rbcar_tags
FROM riftbound.rbcards
WHERE rbcar_name ILIKE '%ahri%'
ORDER BY rbcar_rbset_id, rbcar_id;

-- Step 2: Find the mapping in rbcm_product_card_map
-- Note: for rare/epic, rbpcm_foil should be NULL (legacy) or 'N'
SELECT
    m.rbpcm_id_product,
    m.rbpcm_rbset_id,
    m.rbpcm_rbcar_id,
    m.rbpcm_foil,
    m.rbpcm_match_type,
    m.rbpcm_confidence
FROM riftbound.rbcm_product_card_map m
JOIN riftbound.rbcards c ON c.rbcar_rbset_id = m.rbpcm_rbset_id
                         AND c.rbcar_id       = m.rbpcm_rbcar_id
WHERE c.rbcar_name ILIKE '%ahri%';

-- Step 3: Find prices for mapped products (latest date per product)
SELECT
    p.rbprc_id_product,
    p.rbprc_date,
    p.rbprc_avg7,
    p.rbprc_avg7_foil,
    p.rbprc_low,
    c.rbcar_name,
    m.rbpcm_foil
FROM riftbound.rbcm_price p
JOIN riftbound.rbcm_product_card_map m ON m.rbpcm_id_product = p.rbprc_id_product
JOIN riftbound.rbcards c ON c.rbcar_rbset_id = m.rbpcm_rbset_id
                         AND c.rbcar_id       = m.rbpcm_rbcar_id
WHERE c.rbcar_name ILIKE '%ahri%'
  AND p.rbprc_date = (
      SELECT MAX(rbprc_date)
      FROM riftbound.rbcm_price p2
      WHERE p2.rbprc_id_product = p.rbprc_id_product
  )
ORDER BY p.rbprc_date DESC;

-- Step 4: Verify what _resolve_price would pick
-- For Rare: uses avg7_foil (see collection.py:_resolve_price)
-- If avg7_foil IS NULL but avg7 is populated -> price shows as NULL (BUG)
-- If rbpcm_foil = 'S' on a rare card -> mapping was wrong (rare has no foil)
SELECT
    c.rbcar_name,
    c.rbcar_rarity,
    m.rbpcm_foil,
    p.rbprc_avg7,
    p.rbprc_avg7_foil,
    CASE
        WHEN c.rbcar_rarity IN ('Rare','Epic') OR m.rbpcm_foil = 'S'
        THEN p.rbprc_avg7_foil
        ELSE p.rbprc_avg7
    END AS resolved_price,
    CASE
        WHEN p.rbprc_avg7_foil IS NULL AND c.rbcar_rarity IN ('Rare','Epic')
        THEN 'BUG: avg7_foil is NULL for Rare/Epic - price will not display'
        WHEN m.rbpcm_foil = 'S' AND c.rbcar_rarity IN ('Rare','Epic')
        THEN 'WARN: mapping has foil=S for a Rare/Epic (should be NULL)'
        ELSE 'OK'
    END AS diagnosis
FROM riftbound.rbcm_price p
JOIN riftbound.rbcm_product_card_map m ON m.rbpcm_id_product = p.rbprc_id_product
JOIN riftbound.rbcards c ON c.rbcar_rbset_id = m.rbpcm_rbset_id
                         AND c.rbcar_id       = m.rbpcm_rbcar_id
WHERE c.rbcar_name ILIKE '%ahri%'
  AND p.rbprc_date = (
      SELECT MAX(rbprc_date)
      FROM riftbound.rbcm_price p2
      WHERE p2.rbprc_id_product = p.rbprc_id_product
  );

-- =============================================================================
-- Interpretation guide:
-- - "BUG: avg7_foil is NULL" -> Cardmarket has no foil price for this product.
--   Resolution: either wait for Cardmarket to publish data, or check if the
--   product ID mapped is the wrong variant (wrong idProduct in the mapping).
-- - "WARN: mapping has foil=S for a Rare/Epic" -> auto_match assigned foil='S'
--   to a rare/epic card. This is now prevented by REQ-2. If mapping exists with
--   foil='S', it should be corrected manually to NULL.
-- - "OK" -> code path is correct, price should display.
-- =============================================================================
