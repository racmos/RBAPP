-- =============================================
-- COLLECTION EXTENSIONS - RIFTBOUND MANAGER
-- Base de datos: postgres
-- Esquema: riftbound
--
-- Añade las columnas faltantes sobre riftbound.rbcollection que el
-- modelo SQLAlchemy (app/models/collection.py) y los endpoints ya
-- referencian pero que nunca se habían creado físicamente en la BD.
--
-- Columnas añadidas:
--   rbcol_selling    - Marca si la carta está a la venta (S/N). Default 'N'.
--   rbcol_playset    - Nº de copias reservadas para playset (1, 2 o 3).
--   rbcol_sell_price - Precio de venta unitario (sobre el sobrante).
--   rbcol_condition  - Estado de conservación (MT, NM, EX, GD, LP, PL, PO).
--   rbcol_language   - Idioma de la carta (English, Chinese, Spanish, ...).
-- =============================================

ALTER TABLE riftbound.rbcollection
    ADD COLUMN IF NOT EXISTS rbcol_selling    VARCHAR(1)  DEFAULT 'N',
    ADD COLUMN IF NOT EXISTS rbcol_playset    INTEGER     NULL,
    ADD COLUMN IF NOT EXISTS rbcol_sell_price NUMERIC     NULL,
    ADD COLUMN IF NOT EXISTS rbcol_condition  VARCHAR(8)  NULL,
    ADD COLUMN IF NOT EXISTS rbcol_language   VARCHAR(40) NULL;

-- Check de valores permitidos para rbcol_playset (1, 2 o 3; NULL permitido)
ALTER TABLE riftbound.rbcollection
    DROP CONSTRAINT IF EXISTS rbcollection_playset_chk;

ALTER TABLE riftbound.rbcollection
    ADD CONSTRAINT rbcollection_playset_chk
    CHECK (rbcol_playset IS NULL OR rbcol_playset IN (1, 2, 3));

-- Check de valores permitidos para rbcol_selling (S/N)
ALTER TABLE riftbound.rbcollection
    DROP CONSTRAINT IF EXISTS rbcollection_selling_chk;

ALTER TABLE riftbound.rbcollection
    ADD CONSTRAINT rbcollection_selling_chk
    CHECK (rbcol_selling IN ('Y', 'N', 'S'));  -- 'Y' nuevo / 'S' legacy

-- Normaliza cualquier NULL previo a 'N'
UPDATE riftbound.rbcollection SET rbcol_selling = 'N' WHERE rbcol_selling IS NULL;

-- Comentarios
COMMENT ON COLUMN riftbound.rbcollection.rbcol_selling    IS 'Indica si la carta está a la venta (Y/N)';
COMMENT ON COLUMN riftbound.rbcollection.rbcol_playset    IS 'Nº de copias reservadas para playset (1, 2 o 3)';
COMMENT ON COLUMN riftbound.rbcollection.rbcol_sell_price IS 'Precio de venta unitario sobre el sobrante (quantity - playset)';
COMMENT ON COLUMN riftbound.rbcollection.rbcol_condition  IS 'Estado de conservación (MT, NM, EX, GD, LP, PL, PO)';
COMMENT ON COLUMN riftbound.rbcollection.rbcol_language   IS 'Idioma de la carta (English, Chinese, Spanish, ...)';

-- Índice útil para la vista y exportación filtrada
CREATE INDEX IF NOT EXISTS idx_rbcollection_selling
    ON riftbound.rbcollection (rbcol_user, rbcol_selling);
