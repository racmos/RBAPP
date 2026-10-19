-- =============================================
-- COLLECTION: SYNTHETIC ID PRIMARY KEY - RIFTBOUND MANAGER
-- Base de datos: postgres
-- Esquema: riftbound
--
-- Cambia la PK de rbcollection de la tupla compuesta
--   (rbcol_rbset_id, rbcol_rbcar_id, rbcol_foil, rbcol_user)
-- a una clave sintética rbcol_id BIGSERIAL.
--
-- Motivo: el usuario quiere poder tener varias filas para la MISMA
-- (set, card, foil) cuando difieren en condición, idioma, precio de venta,
-- etc. (ej. 3 unidades GD a 1€ + 2 unidades MT a 2€ de la misma carta).
-- =============================================

BEGIN;

-- 1. Soltar la PK compuesta antigua (su nombre puede variar entre
--    despliegues — comprobamos las dos posibles).
ALTER TABLE riftbound.rbcollection
    DROP CONSTRAINT IF EXISTS rbcollection_pk1;
ALTER TABLE riftbound.rbcollection
    DROP CONSTRAINT IF EXISTS rbcollection_pk;

-- 2. Añadir la nueva columna como BIGSERIAL.
ALTER TABLE riftbound.rbcollection
    ADD COLUMN IF NOT EXISTS rbcol_id BIGSERIAL;

-- 3. Hacerla la nueva PK.
ALTER TABLE riftbound.rbcollection
    ADD CONSTRAINT rbcollection_pk PRIMARY KEY (rbcol_id);

-- 4. Índice de búsqueda por usuario + carta + foil (es el patrón principal
--    de las queries de la app).
CREATE INDEX IF NOT EXISTS idx_rbcollection_user_card_foil
    ON riftbound.rbcollection (rbcol_user, rbcol_rbset_id, rbcol_rbcar_id, rbcol_foil);

COMMENT ON COLUMN riftbound.rbcollection.rbcol_id IS
    'PK sintética. Permite varias filas con la misma (set, card, foil, user) '
    'que difieran en condición, idioma o precio de venta.';

COMMIT;
