-- =============================================
-- RIFTBOUND MANAGER - INSTALLATION SCRIPT
-- =============================================
-- PostgreSQL Database Setup for Riftbound Manager
-- Schema: riftbound
--
-- Usage:
--   psql -h <host> -U <user> -d <database> -f install_db.sql
--
-- Or from within psql:
--   \i install_db.sql
-- =============================================

-- =============================================
-- SECTION 1: CREATE SCHEMA
-- =============================================
CREATE SCHEMA IF NOT EXISTS riftbound;

-- =============================================
-- SECTION 2: MAIN TABLES (from 01_create_tables.sql)
-- =============================================

-- TABLA: rbusers (Usuarios)
DROP TABLE IF EXISTS riftbound.rbusers;

CREATE TABLE riftbound.rbusers (
    id SERIAL PRIMARY KEY,
    username VARCHAR(80) NOT NULL UNIQUE,
    email VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(256),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_rbusers_username ON riftbound.rbusers (username);
CREATE INDEX idx_rbusers_email ON riftbound.rbusers (email);

COMMENT ON TABLE riftbound.rbusers IS 'Usuarios registrados en la aplicacion';
COMMENT ON COLUMN riftbound.rbusers.id IS 'Identificador unico del usuario';
COMMENT ON COLUMN riftbound.rbusers.username IS 'Nombre de usuario unico';
COMMENT ON COLUMN riftbound.rbusers.email IS 'Correo electronico unico';
COMMENT ON COLUMN riftbound.rbusers.password_hash IS 'Hash de la contrasena';
COMMENT ON COLUMN riftbound.rbusers.created_at IS 'Fecha de creacion del usuario';

-- TABLA: rbset (Sets de cartas)
DROP TABLE IF EXISTS riftbound.rbset;

CREATE TABLE riftbound.rbset (
    rbset_id VARCHAR(20) PRIMARY KEY,
    rbset_name VARCHAR(200) NOT NULL,
    rbset_ncard SMALLINT,
    rbset_outdat DATE
);

COMMENT ON TABLE riftbound.rbset IS 'Sets deExpansion de cartas';
COMMENT ON COLUMN riftbound.rbset.rbset_id IS 'Identificador unico del set (codigo)';
COMMENT ON COLUMN riftbound.rbset.rbset_name IS 'Nombre completo del set';
COMMENT ON COLUMN riftbound.rbset.rbset_ncard IS 'Numero total de cartas en el set';
COMMENT ON COLUMN riftbound.rbset.rbset_outdat IS 'Fecha de obsolescencia del set';

-- TABLA: rbcards (Cartas)
DROP TABLE IF EXISTS riftbound.rbcards;

CREATE TABLE riftbound.rbcards (
    rbcar_rbset_id VARCHAR(20) NOT NULL,
    rbcar_id VARCHAR(20) NOT NULL,
    rbcar_name VARCHAR(200) NOT NULL,
    rbcar_domain VARCHAR(50),
    rbcar_type VARCHAR(50),
    rbcar_tags VARCHAR(200),
    rbcar_energy SMALLINT,
    rbcar_power SMALLINT,
    rbcar_might SMALLINT,
    rbcar_ability TEXT,
    rbcar_rarity VARCHAR(20),
    rbcar_artist VARCHAR(100),
    rbcar_banned VARCHAR(1) DEFAULT 'N',
    image_url TEXT,
    image TEXT,
    PRIMARY KEY (rbcar_rbset_id, rbcar_id),
    CONSTRAINT fk_rbcards_set FOREIGN KEY (rbcar_rbset_id) REFERENCES riftbound.rbset(rbset_id)
);

CREATE INDEX idx_rbcards_set_id ON riftbound.rbcards (rbcar_rbset_id);
CREATE INDEX idx_rbcards_name ON riftbound.rbcards (rbcar_name);

COMMENT ON TABLE riftbound.rbcards IS 'Catalogo de cartas del juego';
COMMENT ON COLUMN riftbound.rbcards.rbcar_rbset_id IS 'FK al set al que pertenece la carta';
COMMENT ON COLUMN riftbound.rbcards.rbcar_id IS 'Identificador unico de la carta dentro del set';
COMMENT ON COLUMN riftbound.rbcards.rbcar_name IS 'Nombre de la carta';
COMMENT ON COLUMN riftbound.rbcards.rbcar_domain IS 'Dominio de la carta (Chaos, Calm, Mind, Body, Order, Colorless)';
COMMENT ON COLUMN riftbound.rbcards.rbcar_type IS 'Tipo de carta (Unit, Spell, Gear, Legend, etc.)';
COMMENT ON COLUMN riftbound.rbcards.rbcar_tags IS 'Etiquetas o palabras clave de la carta';
COMMENT ON COLUMN riftbound.rbcards.rbcar_energy IS 'Coste de energia de la carta';
COMMENT ON COLUMN riftbound.rbcards.rbcar_power IS 'Poder de la carta (para unidades)';
COMMENT ON COLUMN riftbound.rbcards.rbcar_might IS 'Fuerza de la carta (para unidades)';
COMMENT ON COLUMN riftbound.rbcards.rbcar_ability IS 'Habilidad especial de la carta';
COMMENT ON COLUMN riftbound.rbcards.rbcar_rarity IS 'Rareza de la carta (Common, Uncommon, Rare, Epic, Legendary)';
COMMENT ON COLUMN riftbound.rbcards.rbcar_artist IS 'Artista que creo la ilustracion';
COMMENT ON COLUMN riftbound.rbcards.rbcar_banned IS 'Si la carta esta banned (S/N)';
COMMENT ON COLUMN riftbound.rbcards.image_url IS 'URL de la imagen de la carta';
COMMENT ON COLUMN riftbound.rbcards.image IS 'Nombre del archivo de imagen';

-- TABLA: rbcollection (Colección de usuario) - with synthetic ID
DROP TABLE IF EXISTS riftbound.rbcollection;

CREATE TABLE riftbound.rbcollection (
    rbcol_id BIGSERIAL PRIMARY KEY,
    rbcol_rbset_id VARCHAR(20) NOT NULL,
    rbcol_rbcar_id VARCHAR(20) NOT NULL,
    rbcol_foil VARCHAR(1) DEFAULT 'N',
    rbcol_quantity VARCHAR(20) NOT NULL,
    rbcol_chadat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    rbcol_user VARCHAR(80),
    rbcol_selling VARCHAR(1) DEFAULT 'N',
    rbcol_playset INTEGER,
    rbcol_sell_price NUMERIC,
    rbcol_condition VARCHAR(8),
    rbcol_language VARCHAR(40),
    CONSTRAINT fk_collection_card FOREIGN KEY (rbcol_rbset_id, rbcol_rbcar_id)
        REFERENCES riftbound.rbcards(rbcar_rbset_id, rbcar_id),
    CONSTRAINT fk_collection_user FOREIGN KEY (rbcol_user) REFERENCES riftbound.rbusers(username)
);

CREATE INDEX idx_rbcollection_user ON riftbound.rbcollection (rbcol_user);
CREATE INDEX idx_rbcollection_set_card ON riftbound.rbcollection (rbcol_rbset_id, rbcol_rbcar_id);
CREATE INDEX idx_rbcollection_user_card_foil ON riftbound.rbcollection (rbcol_user, rbcol_rbset_id, rbcol_rbcar_id, rbcol_foil);
CREATE INDEX idx_rbcollection_selling ON riftbound.rbcollection (rbcol_user, rbcol_selling);

COMMENT ON TABLE riftbound.rbcollection IS 'Coleccion personal de cada usuario';
COMMENT ON COLUMN riftbound.rbcollection.rbcol_id IS 'PK sintética. Permite varias filas con la misma (set, card, foil, user) que difieran en condición, idioma o precio de venta.';
COMMENT ON COLUMN riftbound.rbcollection.rbcol_rbset_id IS 'FK al set de la carta';
COMMENT ON COLUMN riftbound.rbcollection.rbcol_rbcar_id IS 'FK al ID de la carta';
COMMENT ON COLUMN riftbound.rbcollection.rbcol_foil IS 'Si la carta es foil (S/N)';
COMMENT ON COLUMN riftbound.rbcollection.rbcol_quantity IS 'Cantidad de copias de la carta';
COMMENT ON COLUMN riftbound.rbcollection.rbcol_chadat IS 'Fecha de ultimo cambio en la coleccion';
COMMENT ON COLUMN riftbound.rbcollection.rbcol_user IS 'FK al usuario propietario';
COMMENT ON COLUMN riftbound.rbcollection.rbcol_selling IS 'Indica si la carta está a la venta (Y/N)';
COMMENT ON COLUMN riftbound.rbcollection.rbcol_playset IS 'Nº de copias reservadas para playset (1, 2 o 3)';
COMMENT ON COLUMN riftbound.rbcollection.rbcol_sell_price IS 'Precio de venta unitario sobre el sobrante (quantity - playset)';
COMMENT ON COLUMN riftbound.rbcollection.rbcol_condition IS 'Estado de conservación (MT, NM, EX, GD, LP, PL, PO)';
COMMENT ON COLUMN riftbound.rbcollection.rbcol_language IS 'Idioma de la carta (English, Chinese, Spanish, ...)';

-- Constraints for collection extensions
ALTER TABLE riftbound.rbcollection
    DROP CONSTRAINT IF EXISTS rbcollection_playset_chk;
ALTER TABLE riftbound.rbcollection
    ADD CONSTRAINT rbcollection_playset_chk
    CHECK (rbcol_playset IS NULL OR rbcol_playset IN (1, 2, 3));

ALTER TABLE riftbound.rbcollection
    DROP CONSTRAINT IF EXISTS rbcollection_selling_chk;
ALTER TABLE riftbound.rbcollection
    ADD CONSTRAINT rbcollection_selling_chk
    CHECK (rbcol_selling IN ('Y', 'N', 'S'));

-- TABLA: rbdecks (Mazos)
DROP TABLE IF EXISTS riftbound.rbdecks;

CREATE TABLE riftbound.rbdecks (
    id SERIAL PRIMARY KEY,
    rbdck_user VARCHAR(80) NOT NULL,
    rbdck_name VARCHAR(200) NOT NULL,
    rbdck_seq INTEGER DEFAULT 1,
    rbdck_snapshot TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    rbdck_description TEXT,
    rbdck_mode VARCHAR(50) DEFAULT '1v1',
    rbdck_format VARCHAR(50) DEFAULT 'Standard',
    rbdck_max_set VARCHAR(100),
    rbdck_ncards INTEGER DEFAULT 0,
    rbdck_orden NUMERIC,
    rbdck_cards JSONB,
    UNIQUE (rbdck_user, rbdck_name, rbdck_seq),
    CONSTRAINT fk_deck_user FOREIGN KEY (rbdck_user) REFERENCES riftbound.rbusers(username)
);

CREATE INDEX idx_rbdecks_user ON riftbound.rbdecks (rbdck_user);
CREATE INDEX idx_rbdecks_name ON riftbound.rbdecks (rbdck_name);
CREATE INDEX idx_rbdecks_snapshot ON riftbound.rbdecks (rbdck_snapshot);
CREATE INDEX idx_rbdecks_user_name_seq ON riftbound.rbdecks (rbdck_user, rbdck_name, rbdck_seq);

COMMENT ON TABLE riftbound.rbdecks IS 'Mazos creados por usuarios';
COMMENT ON COLUMN riftbound.rbdecks.id IS 'Identificador unico autoincremental del deck';
COMMENT ON COLUMN riftbound.rbdecks.rbdck_user IS 'FK al usuario propietario del deck';
COMMENT ON COLUMN riftbound.rbdecks.rbdck_name IS 'Nombre del deck';
COMMENT ON COLUMN riftbound.rbdecks.rbdck_seq IS 'Secuencial para permitir multiples versiones del mismo deck';
COMMENT ON COLUMN riftbound.rbdecks.rbdck_snapshot IS 'Fecha/hora de creacion del deck (incluye hora, min, seg)';
COMMENT ON COLUMN riftbound.rbdecks.rbdck_description IS 'Descripcion del deck';
COMMENT ON COLUMN riftbound.rbdecks.rbdck_mode IS 'Modo de juego (1v1, Commander, Team, Draft)';
COMMENT ON COLUMN riftbound.rbdecks.rbdck_format IS 'Formato del deck (Standard, Expanded, Classic)';
COMMENT ON COLUMN riftbound.rbdecks.rbdck_max_set IS 'Sets permitidos en el deck';
COMMENT ON COLUMN riftbound.rbdecks.rbdck_ncards IS 'Numero total de cartas en el deck';
COMMENT ON COLUMN riftbound.rbdecks.rbdck_orden IS 'Orden de visualizacion del deck';
COMMENT ON COLUMN riftbound.rbdecks.rbdck_cards IS 'Cartas del deck en formato JSON: {"main": [...], "sideboard": [...]}';

-- TABLA: rbcardmarket (Precios de cartas)
DROP TABLE IF EXISTS riftbound.rbcardmarket;

CREATE TABLE riftbound.rbcardmarket (
    rbcmk_snapshot TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    rbcmk_rbset_id VARCHAR(20) NOT NULL,
    rbcmk_rbcar_id VARCHAR(20) NOT NULL,
    rbcmk_foil VARCHAR(1) DEFAULT 'N',
    rbcmk_name VARCHAR(200) NOT NULL,
    rbcmk_price NUMERIC NOT NULL,
    PRIMARY KEY (rbcmk_snapshot, rbcmk_rbset_id, rbcmk_rbcar_id, rbcmk_foil),
    CONSTRAINT fk_market_card FOREIGN KEY (rbcmk_rbset_id, rbcmk_rbcar_id)
        REFERENCES riftbound.rbcards(rbcar_rbset_id, rbcar_id)
);

CREATE INDEX idx_rbcardmarket_set_card ON riftbound.rbcardmarket (rbcmk_rbset_id, rbcmk_rbcar_id);

COMMENT ON TABLE riftbound.rbcardmarket IS 'Precios de cartas del mercado';
COMMENT ON COLUMN riftbound.rbcardmarket.rbcmk_snapshot IS 'Fecha/hora del precio';
COMMENT ON COLUMN riftbound.rbcardmarket.rbcmk_rbset_id IS 'FK al set de la carta';
COMMENT ON COLUMN riftbound.rbcardmarket.rbcmk_rbcar_id IS 'FK al ID de la carta';
COMMENT ON COLUMN riftbound.rbcardmarket.rbcmk_foil IS 'Si el precio es para version foil (S/N)';
COMMENT ON COLUMN riftbound.rbcardmarket.rbcmk_name IS 'Nombre de la carta';
COMMENT ON COLUMN riftbound.rbcardmarket.rbcmk_price IS 'Precio de la carta';


-- =============================================
-- SECTION 3: CARDMARKET TABLES (from 03_cardmarket_tables.sql)
-- =============================================

-- TABLA: rbcm_products (Productos de Cardmarket)
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

-- TABLA: rbcm_price (Precios diarios de Cardmarket)
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

-- TABLA: rbcm_categories (Categorias de Cardmarket)
DROP TABLE IF EXISTS riftbound.rbcm_categories;

CREATE TABLE riftbound.rbcm_categories (
    rbcat_id INTEGER PRIMARY KEY,
    rbcat_name TEXT NOT NULL
);

COMMENT ON TABLE riftbound.rbcm_categories IS 'Tabla de lookup de categorias de Cardmarket';
COMMENT ON COLUMN riftbound.rbcm_categories.rbcat_id IS 'ID de categoria en Cardmarket';
COMMENT ON COLUMN riftbound.rbcm_categories.rbcat_name IS 'Nombre de la categoria';

-- TABLA: rbcm_expansions (Expansiones de Cardmarket) - with rbset_id mapping
DROP TABLE IF EXISTS riftbound.rbcm_expansions;

CREATE TABLE riftbound.rbcm_expansions (
    rbexp_id INTEGER PRIMARY KEY,
    rbexp_name TEXT,
    rbexp_rbset_id TEXT
);

COMMENT ON TABLE riftbound.rbcm_expansions IS 'Tabla de lookup de expansiones de Cardmarket';
COMMENT ON COLUMN riftbound.rbcm_expansions.rbexp_id IS 'ID de expansion en Cardmarket';
COMMENT ON COLUMN riftbound.rbcm_expansions.rbexp_name IS 'Nombre de la expansion';
COMMENT ON COLUMN riftbound.rbcm_expansions.rbexp_rbset_id IS 'FK blanda al set interno riftbound.rbset.rbset_id. NULL = expansión sin mapear.';

CREATE INDEX IF NOT EXISTS idx_rbcm_expansions_unmapped
    ON riftbound.rbcm_expansions (rbexp_rbset_id)
    WHERE rbexp_rbset_id IS NULL;

-- TABLA: rbcm_load_history (Historial de cargas)
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

COMMENT ON TABLE riftbound.rbcm_load_history IS 'Rastrea cada operacion de carga para validacion de fecha y deteccion de cambios';
COMMENT ON COLUMN riftbound.rbcm_load_history.rblh_id IS 'Identificador unico autoincremental';
COMMENT ON COLUMN riftbound.rbcm_load_history.rblh_date IS 'Fecha de la carga en formato YYYYMMDD';
COMMENT ON COLUMN riftbound.rbcm_load_history.rblh_file_type IS 'Tipo de archivo: singles, nonsingles o price_guide';
COMMENT ON COLUMN riftbound.rbcm_load_history.rblh_hash IS 'Hash SHA-256 del archivo cargado';
COMMENT ON COLUMN riftbound.rbcm_load_history.rblh_rows IS 'Numero de filas procesadas';
COMMENT ON COLUMN riftbound.rbcm_load_history.rblh_status IS 'Estado de la carga: success, error o skipped';
COMMENT ON COLUMN riftbound.rbcm_load_history.rblh_message IS 'Mensaje adicional o descripcion del error';
COMMENT ON COLUMN riftbound.rbcm_load_history.rblh_loaded_at IS 'Fecha y hora de la carga';

-- TABLA: rbcm_product_card_map (Mapa producto-carta) - with foil extension
DROP TABLE IF EXISTS riftbound.rbcm_product_card_map;

CREATE TABLE riftbound.rbcm_product_card_map (
    rbpcm_id_product INTEGER PRIMARY KEY,
    rbpcm_rbset_id TEXT NOT NULL,
    rbpcm_rbcar_id TEXT NOT NULL,
    rbpcm_foil VARCHAR(1) NULL,
    rbpcm_match_type TEXT DEFAULT 'manual',
    rbpcm_confidence NUMERIC,
    CONSTRAINT fk_product_card_map_card FOREIGN KEY (rbpcm_rbset_id, rbpcm_rbcar_id)
        REFERENCES riftbound.rbcards(rbcar_rbset_id, rbcar_id)
);

CREATE INDEX idx_rbcm_product_card_map_rbset_id ON riftbound.rbcm_product_card_map (rbpcm_rbset_id);
CREATE INDEX idx_rbcm_product_card_map_rbcar_id ON riftbound.rbcm_product_card_map (rbpcm_rbcar_id);
CREATE INDEX idx_rbcm_product_card_map_set_card ON riftbound.rbcm_product_card_map (rbpcm_rbset_id, rbpcm_rbcar_id);
CREATE INDEX idx_rbcm_pcm_card_foil ON riftbound.rbcm_product_card_map (rbpcm_rbset_id, rbpcm_rbcar_id, rbpcm_foil);

ALTER TABLE riftbound.rbcm_product_card_map
    DROP CONSTRAINT IF EXISTS rbcm_pcm_foil_chk;
ALTER TABLE riftbound.rbcm_product_card_map
    ADD CONSTRAINT rbcm_pcm_foil_chk
    CHECK (rbpcm_foil IS NULL OR rbpcm_foil IN ('N', 'S'));

COMMENT ON TABLE riftbound.rbcm_product_card_map IS 'Mapea idProduct de Cardmarket a cartas internas de rbcards';
COMMENT ON COLUMN riftbound.rbcm_product_card_map.rbpcm_id_product IS 'idProduct de Cardmarket';
COMMENT ON COLUMN riftbound.rbcm_product_card_map.rbpcm_rbset_id IS 'FK al set interno de la carta';
COMMENT ON COLUMN riftbound.rbcm_product_card_map.rbpcm_rbcar_id IS 'FK al ID interno de la carta';
COMMENT ON COLUMN riftbound.rbcm_product_card_map.rbpcm_foil IS 'N=normal, S=foil, NULL=no aplica (rare/epic) o mapping legacy';
COMMENT ON COLUMN riftbound.rbcm_product_card_map.rbpcm_match_type IS 'Tipo de mapeo: auto o manual';
COMMENT ON COLUMN riftbound.rbcm_product_card_map.rbpcm_confidence IS 'Nivel de confianza del mapeo automatico';

-- TABLA: rbcm_ignored (Productos ignorados por el usuario)
DROP TABLE IF EXISTS riftbound.rbcm_ignored;

CREATE TABLE riftbound.rbcm_ignored (
    rbig_id_product INT NOT NULL,
    rbig_name TEXT NOT NULL,
    rbig_ignored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (rbig_id_product, rbig_name)
);

CREATE INDEX IF NOT EXISTS idx_rbcm_ignored_id ON riftbound.rbcm_ignored(rbig_id_product);

COMMENT ON TABLE riftbound.rbcm_ignored IS 'Productos ignorados explicitamente por el usuario en el navegador de mappings';
COMMENT ON COLUMN riftbound.rbcm_ignored.rbig_id_product IS 'idProduct de Cardmarket';
COMMENT ON COLUMN riftbound.rbcm_ignored.rbig_name IS 'Nombre del producto (parte de la PK compuesta para distinguir variantes)';
COMMENT ON COLUMN riftbound.rbcm_ignored.rbig_ignored_at IS 'Cuando fue ignorado el producto';

-- TABLA: rbproducts (Tabla maestra de productos)
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

COMMENT ON TABLE riftbound.rbproducts IS 'Tabla maestra de productos curada (uso futuro)';
COMMENT ON COLUMN riftbound.rbproducts.rbpdt_id_set IS 'FK al set interno de Riftbound';
COMMENT ON COLUMN riftbound.rbproducts.rbpdt_id_product IS 'ID del producto en Cardmarket';
COMMENT ON COLUMN riftbound.rbproducts.rbpdt_name IS 'Nombre del producto';
COMMENT ON COLUMN riftbound.rbproducts.rbpdt_description IS 'Descripcion del producto';
COMMENT ON COLUMN riftbound.rbproducts.rbpdt_type IS 'Tipo de producto: single o nonsingle';
COMMENT ON COLUMN riftbound.rbproducts.rbpdt_image_url IS 'URL de la imagen del producto';
COMMENT ON COLUMN riftbound.rbproducts.rbpdt_image IS 'Nombre del archivo de imagen del producto';


-- =============================================
-- SECTION 4: SAMPLE DATA (from 02_sample_data.sql)
-- =============================================

-- Insertar usuario de prueba (password: test123)
INSERT INTO riftbound.rbusers (username, email, password_hash)
VALUES ('test', 'test@test.com', 'pbkdf2:sha256:260000$test$5ecc2fa2c82c6a82be3c16d2d5c0a7d8e9f1b2c3d4e5f6a7b8c9d0e1f2a3b4')
ON CONFLICT (username) DO NOTHING;

-- Insertar sets de ejemplo
INSERT INTO riftbound.rbset (rbset_id, rbset_name, rbset_ncard, rbset_outdat)
VALUES
    ('OGN', 'Origins', 210, '2024-01-01'),
    ('WIS', 'Wisdom', 180, '2024-06-01'),
    ('FER', 'Feros', 180, '2024-09-01'),
    ('DRA', 'Dragan', 200, '2025-01-01')
ON CONFLICT (rbset_id) DO NOTHING;

-- Insertar algunas cartas de ejemplo
INSERT INTO riftbound.rbcards (rbcar_rbset_id, rbcar_id, rbcar_name, rbcar_type, rbcar_energy, rbcar_power, rbcar_might, rbcar_rarity, rbcar_domain)
VALUES
    ('OGN', '001', 'Flame Imp', 'Unit', 2, 3, 2, 'Common', 'Chaos'),
    ('OGN', '002', 'Ice Shield', 'Spell', 1, NULL, NULL, 'Common', 'Calm'),
    ('OGN', '003', 'Shadow Assassin', 'Unit', 3, 4, 1, 'Rare', 'Chaos'),
    ('WIS', '001', 'Mind Reader', 'Unit', 2, 2, 3, 'Uncommon', 'Mind'),
    ('WIS', '002', 'Wisdom Crystal', 'Gear', 1, NULL, NULL, 'Rare', 'Mind'),
    ('FER', '001', 'Iron Golem', 'Unit', 4, 5, 5, 'Epic', 'Body'),
    ('DRA', '001', 'Dragon King', 'Legend', 6, 8, 8, 'Legendary', 'Order')
ON CONFLICT (rbcar_rbset_id, rbcar_id) DO NOTHING;

-- Insertar algunos precios de mercado
INSERT INTO riftbound.rbcardmarket (rbcmk_snapshot, rbcmk_rbset_id, rbcmk_rbcar_id, rbcmk_foil, rbcmk_name, rbcmk_price)
VALUES
    ('2026-01-01 10:00:00', 'OGN', '001', 'N', 'Flame Imp', 0.25),
    ('2026-01-01 10:00:00', 'OGN', '002', 'N', 'Ice Shield', 0.10),
    ('2026-01-01 10:00:00', 'OGN', '003', 'N', 'Shadow Assassin', 2.50),
    ('2026-01-01 10:00:00', 'WIS', '001', 'N', 'Mind Reader', 0.50),
    ('2026-01-01 10:00:00', 'WIS', '002', 'N', 'Wisdom Crystal', 1.00),
    ('2026-01-01 10:00:00', 'FER', '001', 'N', 'Iron Golem', 5.00),
    ('2026-01-01 10:00:00', 'DRA', '001', 'N', 'Dragon King', 15.00)
ON CONFLICT DO NOTHING;

-- Insertar ejemplo de colección
INSERT INTO riftbound.rbcollection (rbcol_rbset_id, rbcol_rbcar_id, rbcol_foil, rbcol_quantity, rbcol_chadat, rbcol_user)
VALUES
    ('OGN', '001', 'N', '3', CURRENT_TIMESTAMP, 'test'),
    ('OGN', '002', 'N', '1', CURRENT_TIMESTAMP, 'test'),
    ('WIS', '001', 'N', '2', CURRENT_TIMESTAMP, 'test')
ON CONFLICT DO NOTHING;

-- Insertar ejemplo de deck
INSERT INTO riftbound.rbdecks (rbdck_user, rbdck_name, rbdck_seq, rbdck_snapshot, rbdck_description, rbdck_mode, rbdck_format, rbdck_ncards, rbdck_cards)
VALUES
    ('test', 'My First Deck', 1, CURRENT_TIMESTAMP, 'A test deck', '1v1', 'Standard', 4,
     '{"main": [{"set": "OGN", "id": "001", "qty": 3}, {"set": "WIS", "id": "001", "qty": 1}], "sideboard": []}')
ON CONFLICT DO NOTHING;


-- =============================================
-- SECTION 5: VERIFICATION
-- =============================================
DO $$
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Riftbound Manager DB installed successfully!';
    RAISE NOTICE '========================================';
END $$;

-- Display table counts
SELECT 'rbusers' AS table_name, COUNT(*) AS record_count FROM riftbound.rbusers
UNION ALL
SELECT 'rbset', COUNT(*) FROM riftbound.rbset
UNION ALL
SELECT 'rbcards', COUNT(*) FROM riftbound.rbcards
UNION ALL
SELECT 'rbcollection', COUNT(*) FROM riftbound.rbcollection
UNION ALL
SELECT 'rbdecks', COUNT(*) FROM riftbound.rbdecks
UNION ALL
SELECT 'rbcardmarket', COUNT(*) FROM riftbound.rbcardmarket
UNION ALL
SELECT 'rbcm_products', COUNT(*) FROM riftbound.rbcm_products
UNION ALL
SELECT 'rbcm_price', COUNT(*) FROM riftbound.rbcm_price
UNION ALL
SELECT 'rbcm_product_card_map', COUNT(*) FROM riftbound.rbcm_product_card_map
UNION ALL
SELECT 'rbcm_ignored', COUNT(*) FROM riftbound.rbcm_ignored;

-- =============================================
-- END OF INSTALLATION SCRIPT
-- =============================================