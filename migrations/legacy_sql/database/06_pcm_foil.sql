-- =============================================
-- PRODUCT-CARD MAP FOIL EXTENSION - RIFTBOUND MANAGER
-- Base de datos: postgres
-- Esquema: riftbound
--
-- Añade rbpcm_foil a rbcm_product_card_map para distinguir si un idProduct
-- de Cardmarket apunta a la versión normal o foil de una carta interna.
--
-- Necesario porque las cartas common/uncommon tienen una ÚNICA entrada en
-- rbcards (sin distinguir N/S), pero en Cardmarket existen como 2 productos
-- separados (normal + foil) y los precios son distintos.
--
-- Valores:
--   'N'  -> el idProduct representa la versión normal de esa carta
--   'S'  -> el idProduct representa la versión foil
--   NULL -> no aplica (rare/epic, promo, etc.) o mapping legacy sin clasificar
-- =============================================

ALTER TABLE riftbound.rbcm_product_card_map
    ADD COLUMN IF NOT EXISTS rbpcm_foil VARCHAR(1) NULL;

ALTER TABLE riftbound.rbcm_product_card_map
    DROP CONSTRAINT IF EXISTS rbcm_pcm_foil_chk;

ALTER TABLE riftbound.rbcm_product_card_map
    ADD CONSTRAINT rbcm_pcm_foil_chk
    CHECK (rbpcm_foil IS NULL OR rbpcm_foil IN ('N', 'S'));

COMMENT ON COLUMN riftbound.rbcm_product_card_map.rbpcm_foil
    IS 'N=normal, S=foil, NULL=no aplica (rare/epic) o mapping legacy';

-- Índice para queries que joinen por (rbset_id, rbcar_id, foil)
CREATE INDEX IF NOT EXISTS idx_rbcm_pcm_card_foil
    ON riftbound.rbcm_product_card_map (rbpcm_rbset_id, rbpcm_rbcar_id, rbpcm_foil);
