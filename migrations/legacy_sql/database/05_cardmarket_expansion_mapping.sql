-- =============================================
-- CARDMARKET EXPANSION MAPPING - RIFTBOUND MANAGER
-- Base de datos: postgres
-- Esquema: riftbound
--
-- Añade la columna rbexp_rbset_id a riftbound.rbcm_expansions para enlazar
-- cada expansión de Cardmarket con el set interno (rbset.rbset_id). Este
-- enlace es la clave para que:
--   1. El auto-matching de idProduct -> (rbset_id, rbcar_id) sepa a qué
--      set de la app corresponde cada producto.
--   2. La UI pueda detectar expansiones Cardmarket nuevas sin mapear y
--      disparar el botón "Nueva expansión" para pedir al usuario el
--      rbset_id equivalente (o crearlo si no existe).
-- =============================================

ALTER TABLE riftbound.rbcm_expansions
    ADD COLUMN IF NOT EXISTS rbexp_rbset_id TEXT NULL;

COMMENT ON COLUMN riftbound.rbcm_expansions.rbexp_rbset_id
    IS 'FK blanda (sin constraint) al set interno riftbound.rbset.rbset_id. '
       'NULL = expansión de Cardmarket sin mapear todavía al catálogo de la app.';

-- Índice para filtrar rápido las expansiones sin mapear
CREATE INDEX IF NOT EXISTS idx_rbcm_expansions_unmapped
    ON riftbound.rbcm_expansions (rbexp_rbset_id)
    WHERE rbexp_rbset_id IS NULL;
