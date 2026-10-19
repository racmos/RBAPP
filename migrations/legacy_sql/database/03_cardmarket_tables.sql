-- =============================================
-- CARDMARKET TABLES - RIFTBOUND MANAGER
-- Base de datos: postgres
-- Esquema: riftbound
-- =============================================

-- =============================================
-- ALTER TABLE: rbdecks (Typo fix)
-- Rename rbdck_decription → rbdck_description
-- =============================================
ALTER TABLE riftbound.rbdecks RENAME COLUMN rbdck_decription TO rbdck_description;

COMMENT ON COLUMN riftbound.rbdecks.rbdck_description IS 'Descripcion del deck';

-- =============================================
-- TABLA: rbcm_products (Productos de Cardmarket)
-- Compatible con modelo app/models/cardmarket.py: RbcmProduct
-- =============================================
DROP TABLE IF EXISTS riftbound.rbcm_products;

CREATE TABLE riftbound.rbcm_products (
    rbprd_date TEXT NOT NULL,
    rbprd_id_product INTEGER NOT NULL,
    rbprd_name TEXT NOT NULL,
    rbprd_id_category INTEGER,
    rbprd_category_name TEXT,
    rbprd_id_expansion INTEGER,
    rbprd_id_metacard INTEGER,
    rbprd_date_added TEXT,
    rbprd_type TEXT NOT NULL,
    PRIMARY KEY (rbprd_date, rbprd_id_product)
);

CREATE INDEX idx_rbcm_products_date ON riftbound.rbcm_products (rbprd_date);
CREATE INDEX idx_rbcm_products_id_product ON riftbound.rbcm_products (rbprd_id_product);
CREATE INDEX idx_rbcm_products_id_expansion ON riftbound.rbcm_products (rbprd_id_expansion);
CREATE INDEX idx_rbcm_products_type ON riftbound.rbcm_products (rbprd_type);

-- Comentarios para rbcm_products
COMMENT ON TABLE riftbound.rbcm_products IS 'Datos brutos de productos de Cardmarket por fecha';
COMMENT ON COLUMN riftbound.rbcm_products.rbprd_date IS 'Fecha de carga en formato YYYYMMDD';
COMMENT ON COLUMN riftbound.rbcm_products.rbprd_id_product IS 'idProduct de Cardmarket';
COMMENT ON COLUMN riftbound.rbcm_products.rbprd_name IS 'Nombre del producto en Cardmarket';
COMMENT ON COLUMN riftbound.rbcm_products.rbprd_id_category IS 'ID de categoria en Cardmarket';
COMMENT ON COLUMN riftbound.rbcm_products.rbprd_category_name IS 'Nombre de la categoria en Cardmarket';
COMMENT ON COLUMN riftbound.rbcm_products.rbprd_id_expansion IS 'ID de expansion en Cardmarket';
COMMENT ON COLUMN riftbound.rbcm_products.rbprd_id_metacard IS 'ID de metacarta en Cardmarket';
COMMENT ON COLUMN riftbound.rbcm_products.rbprd_date_added IS 'Fecha de alta del producto en Cardmarket (del JSON)';
COMMENT ON COLUMN riftbound.rbcm_products.rbprd_type IS 'Tipo de producto: single o nonsingle';

-- =============================================
-- TABLA: rbcm_price (Precios diarios de Cardmarket)
-- Compatible con modelo app/models/cardmarket.py: RbcmPrice
-- =============================================
DROP TABLE IF EXISTS riftbound.rbcm_price;

CREATE TABLE riftbound.rbcm_price (
    rbprc_date TEXT NOT NULL,
    rbprc_id_product INTEGER NOT NULL,
    rbprc_id_category INTEGER,
    rbprc_avg NUMERIC,
    rbprc_low NUMERIC,
    rbprc_trend NUMERIC,
    rbprc_avg1 NUMERIC,
    rbprc_avg7 NUMERIC,
    rbprc_avg30 NUMERIC,
    rbprc_avg_foil NUMERIC,
    rbprc_low_foil NUMERIC,
    rbprc_trend_foil NUMERIC,
    rbprc_avg1_foil NUMERIC,
    rbprc_avg7_foil NUMERIC,
    rbprc_avg30_foil NUMERIC,
    rbprc_low_ex NUMERIC,
    PRIMARY KEY (rbprc_date, rbprc_id_product)
);

CREATE INDEX idx_rbcm_price_date ON riftbound.rbcm_price (rbprc_date);
CREATE INDEX idx_rbcm_price_id_product ON riftbound.rbcm_price (rbprc_id_product);
CREATE INDEX idx_rbcm_price_id_category ON riftbound.rbcm_price (rbprc_id_category);

-- Comentarios para rbcm_price
COMMENT ON TABLE riftbound.rbcm_price IS 'Snapshots diarios de precios de Cardmarket';
COMMENT ON COLUMN riftbound.rbcm_price.rbprc_date IS 'Fecha del precio en formato YYYYMMDD';
COMMENT ON COLUMN riftbound.rbcm_price.rbprc_id_product IS 'idProduct de Cardmarket';
COMMENT ON COLUMN riftbound.rbcm_price.rbprc_id_category IS 'ID de categoria del producto';
COMMENT ON COLUMN riftbound.rbcm_price.rbprc_avg IS 'Precio medio';
COMMENT ON COLUMN riftbound.rbcm_price.rbprc_low IS 'Precio minimo';
COMMENT ON COLUMN riftbound.rbcm_price.rbprc_trend IS 'Precio tendencia';
COMMENT ON COLUMN riftbound.rbcm_price.rbprc_avg1 IS 'Precio medio 1 dia';
COMMENT ON COLUMN riftbound.rbcm_price.rbprc_avg7 IS 'Precio medio 7 dias';
COMMENT ON COLUMN riftbound.rbcm_price.rbprc_avg30 IS 'Precio medio 30 dias';
COMMENT ON COLUMN riftbound.rbcm_price.rbprc_avg_foil IS 'Precio medio foil';
COMMENT ON COLUMN riftbound.rbcm_price.rbprc_low_foil IS 'Precio minimo foil';
COMMENT ON COLUMN riftbound.rbcm_price.rbprc_trend_foil IS 'Precio tendencia foil';
COMMENT ON COLUMN riftbound.rbcm_price.rbprc_avg1_foil IS 'Precio medio foil 1 dia';
COMMENT ON COLUMN riftbound.rbcm_price.rbprc_avg7_foil IS 'Precio medio foil 7 dias';
COMMENT ON COLUMN riftbound.rbcm_price.rbprc_avg30_foil IS 'Precio medio foil 30 dias';
COMMENT ON COLUMN riftbound.rbcm_price.rbprc_low_ex IS 'Precio minimo ex+ (excluye foil)';

-- =============================================
-- TABLA: rbcm_categories (Categorias de Cardmarket)
-- Compatible con modelo app/models/cardmarket.py: RbcmCategory
-- =============================================
DROP TABLE IF EXISTS riftbound.rbcm_categories;

CREATE TABLE riftbound.rbcm_categories (
    rbcat_id INTEGER PRIMARY KEY,
    rbcat_name TEXT NOT NULL
);

-- Comentarios para rbcm_categories
COMMENT ON TABLE riftbound.rbcm_categories IS 'Tabla de lookup de categorias de Cardmarket';
COMMENT ON COLUMN riftbound.rbcm_categories.rbcat_id IS 'ID de categoria en Cardmarket';
COMMENT ON COLUMN riftbound.rbcm_categories.rbcat_name IS 'Nombre de la categoria';

-- =============================================
-- TABLA: rbcm_expansions (Expansiones de Cardmarket)
-- Compatible con modelo app/models/cardmarket.py: RbcmExpansion
-- =============================================
DROP TABLE IF EXISTS riftbound.rbcm_expansions;

CREATE TABLE riftbound.rbcm_expansions (
    rbexp_id INTEGER PRIMARY KEY,
    rbexp_name TEXT
);

-- Comentarios para rbcm_expansions
COMMENT ON TABLE riftbound.rbcm_expansions IS 'Tabla de lookup de expansiones de Cardmarket';
COMMENT ON COLUMN riftbound.rbcm_expansions.rbexp_id IS 'ID de expansion en Cardmarket';
COMMENT ON COLUMN riftbound.rbcm_expansions.rbexp_name IS 'Nombre de la expansion';

-- =============================================
-- TABLA: rbcm_load_history (Historial de cargas)
-- Compatible con modelo app/models/cardmarket.py: RbcmLoadHistory
-- =============================================
DROP TABLE IF EXISTS riftbound.rbcm_load_history;

CREATE TABLE riftbound.rbcm_load_history (
    rblh_id SERIAL PRIMARY KEY,
    rblh_date TEXT NOT NULL,
    rblh_file_type TEXT NOT NULL,
    rblh_hash TEXT NOT NULL,
    rblh_rows INTEGER,
    rblh_status TEXT DEFAULT 'success',
    rblh_message TEXT,
    rblh_loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_rbcm_load_history_date ON riftbound.rbcm_load_history (rblh_date);
CREATE INDEX idx_rbcm_load_history_file_type ON riftbound.rbcm_load_history (rblh_file_type);
CREATE INDEX idx_rbcm_load_history_status ON riftbound.rbcm_load_history (rblh_status);

-- Comentarios para rbcm_load_history
COMMENT ON TABLE riftbound.rbcm_load_history IS 'Rastrea cada operacion de carga para validacion de fecha y deteccion de cambios';
COMMENT ON COLUMN riftbound.rbcm_load_history.rblh_id IS 'Identificador unico autoincremental';
COMMENT ON COLUMN riftbound.rbcm_load_history.rblh_date IS 'Fecha de la carga en formato YYYYMMDD';
COMMENT ON COLUMN riftbound.rbcm_load_history.rblh_file_type IS 'Tipo de archivo: singles, nonsingles o price_guide';
COMMENT ON COLUMN riftbound.rbcm_load_history.rblh_hash IS 'Hash SHA-256 del archivo cargado';
COMMENT ON COLUMN riftbound.rbcm_load_history.rblh_rows IS 'Numero de filas procesadas';
COMMENT ON COLUMN riftbound.rbcm_load_history.rblh_status IS 'Estado de la carga: success, error o skipped';
COMMENT ON COLUMN riftbound.rbcm_load_history.rblh_message IS 'Mensaje adicional o descripcion del error';
COMMENT ON COLUMN riftbound.rbcm_load_history.rblh_loaded_at IS 'Fecha y hora de la carga';

-- =============================================
-- TABLA: rbcm_product_card_map (Mapa producto-carta)
-- Compatible con modelo app/models/cardmarket.py: RbcmProductCardMap
-- =============================================
DROP TABLE IF EXISTS riftbound.rbcm_product_card_map;

CREATE TABLE riftbound.rbcm_product_card_map (
    rbpcm_id_product INTEGER PRIMARY KEY,
    rbpcm_rbset_id TEXT NOT NULL,
    rbpcm_rbcar_id TEXT NOT NULL,
    rbpcm_match_type TEXT DEFAULT 'manual',
    rbpcm_confidence NUMERIC,
    CONSTRAINT fk_product_card_map_card FOREIGN KEY (rbpcm_rbset_id, rbpcm_rbcar_id)
        REFERENCES riftbound.rbcards(rbcar_rbset_id, rbcar_id)
);

CREATE INDEX idx_rbcm_product_card_map_rbset_id ON riftbound.rbcm_product_card_map (rbpcm_rbset_id);
CREATE INDEX idx_rbcm_product_card_map_rbcar_id ON riftbound.rbcm_product_card_map (rbpcm_rbcar_id);
CREATE INDEX idx_rbcm_product_card_map_set_card ON riftbound.rbcm_product_card_map (rbpcm_rbset_id, rbpcm_rbcar_id);

-- Comentarios para rbcm_product_card_map
COMMENT ON TABLE riftbound.rbcm_product_card_map IS 'Mapea idProduct de Cardmarket a cartas internas de rbcards';
COMMENT ON COLUMN riftbound.rbcm_product_card_map.rbpcm_id_product IS 'idProduct de Cardmarket';
COMMENT ON COLUMN riftbound.rbcm_product_card_map.rbpcm_rbset_id IS 'FK al set interno de la carta';
COMMENT ON COLUMN riftbound.rbcm_product_card_map.rbpcm_rbcar_id IS 'FK al ID interno de la carta';
COMMENT ON COLUMN riftbound.rbcm_product_card_map.rbpcm_match_type IS 'Tipo de mapeo: auto o manual';
COMMENT ON COLUMN riftbound.rbcm_product_card_map.rbpcm_confidence IS 'Nivel de confianza del mapeo automatico';

-- =============================================
-- TABLA: rbproducts (Tabla maestra de productos)
-- Compatible con modelo app/models/cardmarket.py: RbProducts
-- =============================================
DROP TABLE IF EXISTS riftbound.rbproducts;

CREATE TABLE riftbound.rbproducts (
    rbpdt_id_set TEXT NOT NULL,
    rbpdt_id_product INTEGER NOT NULL,
    rbpdt_name TEXT NOT NULL,
    rbpdt_description TEXT,
    rbpdt_type TEXT,
    rbpdt_image_url TEXT,
    rbpdt_image TEXT,
    PRIMARY KEY (rbpdt_id_set, rbpdt_id_product),
    CONSTRAINT fk_rbproducts_set FOREIGN KEY (rbpdt_id_set)
        REFERENCES riftbound.rbset(rbset_id)
);

CREATE INDEX idx_rbproducts_id_set ON riftbound.rbproducts (rbpdt_id_set);
CREATE INDEX idx_rbproducts_id_product ON riftbound.rbproducts (rbpdt_id_product);
CREATE INDEX idx_rbproducts_type ON riftbound.rbproducts (rbpdt_type);

-- Comentarios para rbproducts
COMMENT ON TABLE riftbound.rbproducts IS 'Tabla maestra de productos curada (uso futuro)';
COMMENT ON COLUMN riftbound.rbproducts.rbpdt_id_set IS 'FK al set interno de Riftbound';
COMMENT ON COLUMN riftbound.rbproducts.rbpdt_id_product IS 'ID del producto en Cardmarket';
COMMENT ON COLUMN riftbound.rbproducts.rbpdt_name IS 'Nombre del producto';
COMMENT ON COLUMN riftbound.rbproducts.rbpdt_description IS 'Descripcion del producto';
COMMENT ON COLUMN riftbound.rbproducts.rbpdt_type IS 'Tipo de producto: single o nonsingle';
COMMENT ON COLUMN riftbound.rbproducts.rbpdt_image_url IS 'URL de la imagen del producto';
COMMENT ON COLUMN riftbound.rbproducts.rbpdt_image IS 'Nombre del archivo de imagen del producto';
