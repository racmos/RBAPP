-- ============================================================================
-- DIAGNOSTIC: revisar mappings Cardmarket potencialmente incorrectos
-- ============================================================================
-- Pegar en psql / DBeaver. Cada bloque es independiente.

-- ----------------------------------------------------------------------------
-- 1. Mismos (rbset_id, rbcar_id, rbpcm_foil) usados por más de un idProduct.
--    NO debería ocurrir nunca: el endpoint manual y el auto-matcher lo
--    impiden, así que estas filas vienen de cargas legacy o inserciones
--    directas en BD.
-- ----------------------------------------------------------------------------
SELECT
    rbpcm_rbset_id,
    rbpcm_rbcar_id,
    rbpcm_foil,
    COUNT(*)                  AS n_mappings,
    array_agg(rbpcm_id_product ORDER BY rbpcm_id_product) AS id_products
FROM riftbound.rbcm_product_card_map
GROUP BY rbpcm_rbset_id, rbpcm_rbcar_id, rbpcm_foil
HAVING COUNT(*) > 1
ORDER BY n_mappings DESC, rbpcm_rbset_id, rbpcm_rbcar_id;

-- ----------------------------------------------------------------------------
-- 2. Mappings que apuntan a una rbcar_id que NO EXISTE en rbcards.
--    Indica que el matching automático apuntó a un set/carta inexistente.
-- ----------------------------------------------------------------------------
SELECT
    m.rbpcm_id_product,
    m.rbpcm_rbset_id,
    m.rbpcm_rbcar_id,
    m.rbpcm_foil,
    m.rbpcm_match_type,
    m.rbpcm_confidence
FROM riftbound.rbcm_product_card_map m
LEFT JOIN riftbound.rbcards c
       ON c.rbcar_rbset_id = m.rbpcm_rbset_id
      AND c.rbcar_id       = m.rbpcm_rbcar_id
WHERE c.rbcar_rbset_id IS NULL
ORDER BY m.rbpcm_match_type, m.rbpcm_rbset_id, m.rbpcm_rbcar_id;

-- ----------------------------------------------------------------------------
-- 3. Cartas internas con MÚLTIPLES idProduct mapeados.
--    Esperado para common/uncommon (normal + foil): n=2.
--    Si n=3+ revisar manualmente — puede ser correcto (variantes promo)
--    o incorrecto.
-- ----------------------------------------------------------------------------
SELECT
    m.rbpcm_rbset_id,
    m.rbpcm_rbcar_id,
    c.rbcar_name,
    c.rbcar_rarity,
    COUNT(*)                                   AS n_products,
    array_agg(m.rbpcm_id_product ORDER BY m.rbpcm_id_product) AS id_products,
    array_agg(COALESCE(m.rbpcm_foil, '_'))     AS foils
FROM riftbound.rbcm_product_card_map m
LEFT JOIN riftbound.rbcards c
       ON c.rbcar_rbset_id = m.rbpcm_rbset_id
      AND c.rbcar_id       = m.rbpcm_rbcar_id
GROUP BY m.rbpcm_rbset_id, m.rbpcm_rbcar_id, c.rbcar_name, c.rbcar_rarity
HAVING COUNT(*) > 1
ORDER BY n_products DESC, m.rbpcm_rbset_id, m.rbpcm_rbcar_id;

-- ----------------------------------------------------------------------------
-- 4. Mappings rare/epic con rbpcm_foil != NULL (deberían ser NULL — rare/epic
--    no tienen foil). Probablemente el auto-matcher se equivocó al expandir
--    slots.
-- ----------------------------------------------------------------------------
SELECT
    m.rbpcm_id_product,
    m.rbpcm_rbset_id,
    m.rbpcm_rbcar_id,
    c.rbcar_name,
    c.rbcar_rarity,
    m.rbpcm_foil,
    m.rbpcm_match_type
FROM riftbound.rbcm_product_card_map m
JOIN riftbound.rbcards c
  ON c.rbcar_rbset_id = m.rbpcm_rbset_id
 AND c.rbcar_id       = m.rbpcm_rbcar_id
WHERE LOWER(COALESCE(c.rbcar_rarity, '')) IN ('rare', 'epic')
  AND m.rbpcm_foil IS NOT NULL
ORDER BY c.rbcar_rarity, m.rbpcm_rbset_id, m.rbpcm_rbcar_id;

-- ----------------------------------------------------------------------------
-- 5. Common/uncommon SIN versión foil mapeada.
--    Revisar si el producto foil existe en Cardmarket y por qué no se mapeó.
-- ----------------------------------------------------------------------------
SELECT
    c.rbcar_rbset_id,
    c.rbcar_id,
    c.rbcar_name,
    c.rbcar_rarity,
    bool_or(m.rbpcm_foil = 'N') AS tiene_normal,
    bool_or(m.rbpcm_foil = 'S') AS tiene_foil,
    array_agg(DISTINCT m.rbpcm_foil) AS foils_mapeados
FROM riftbound.rbcards c
LEFT JOIN riftbound.rbcm_product_card_map m
       ON m.rbpcm_rbset_id = c.rbcar_rbset_id
      AND m.rbpcm_rbcar_id = c.rbcar_id
WHERE LOWER(COALESCE(c.rbcar_rarity, '')) IN ('common', 'uncommon')
  AND c.rbcar_rbset_id NOT LIKE '%X'
GROUP BY c.rbcar_rbset_id, c.rbcar_id, c.rbcar_name, c.rbcar_rarity
HAVING NOT (bool_or(m.rbpcm_foil = 'N') AND bool_or(m.rbpcm_foil = 'S'))
ORDER BY c.rbcar_rbset_id, c.rbcar_id;

-- ----------------------------------------------------------------------------
-- 6. Productos mapeados cuyo precio (último día) NO encaja con la posición
--    esperada de la variante. Esto compara el precio low del producto con
--    la mediana de los demás productos del mismo metacard. Productos con un
--    desviación grande pueden indicar un mapping invertido.
-- ----------------------------------------------------------------------------
WITH latest_price AS (
    SELECT rbprc_id_product,
           MAX(rbprc_date) AS d
    FROM riftbound.rbcm_price
    GROUP BY rbprc_id_product
),
prices AS (
    SELECT p.rbprc_id_product,
           COALESCE(p.rbprc_low, p.rbprc_avg7, p.rbprc_avg7_foil, 0)::numeric AS price
    FROM riftbound.rbcm_price p
    JOIN latest_price lp
      ON lp.rbprc_id_product = p.rbprc_id_product
     AND lp.d = p.rbprc_date
),
metacard_stats AS (
    SELECT pr.rbprd_id_metacard,
           COUNT(*) AS n,
           AVG(pp.price) AS avg_price,
           STDDEV_POP(pp.price) AS sd_price
    FROM riftbound.rbcm_products pr
    JOIN prices pp ON pp.rbprc_id_product = pr.rbprd_id_product
    WHERE pr.rbprd_id_metacard IS NOT NULL
    GROUP BY pr.rbprd_id_metacard
    HAVING COUNT(*) >= 2
)
SELECT
    pr.rbprd_id_product,
    pr.rbprd_name,
    pp.price                                        AS price,
    ms.avg_price                                    AS metacard_avg,
    ms.sd_price                                     AS metacard_sd,
    m.rbpcm_rbset_id,
    m.rbpcm_rbcar_id,
    m.rbpcm_foil,
    c.rbcar_name,
    c.rbcar_rarity
FROM riftbound.rbcm_products pr
JOIN prices pp           ON pp.rbprc_id_product = pr.rbprd_id_product
JOIN metacard_stats ms   ON ms.rbprd_id_metacard = pr.rbprd_id_metacard
LEFT JOIN riftbound.rbcm_product_card_map m ON m.rbpcm_id_product = pr.rbprd_id_product
LEFT JOIN riftbound.rbcards c
       ON c.rbcar_rbset_id = m.rbpcm_rbset_id
      AND c.rbcar_id       = m.rbpcm_rbcar_id
WHERE ms.sd_price IS NOT NULL AND ms.sd_price > 0
  AND ABS(pp.price - ms.avg_price) > (ms.sd_price * 1.5)  -- outliers
ORDER BY ABS(pp.price - ms.avg_price) DESC
LIMIT 50;
