-- =============================================
-- ESTRUCTURA DE BASE DE DATOS - RIFTBOUND MANAGER
-- Base de datos: postgres
-- Esquema: riftbound
-- =============================================

-- =============================================
-- TABLA: rbusers (Usuarios)
-- Compatible con modelo app/models/user.py
-- =============================================
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

-- Comentarios para rbusers
COMMENT ON TABLE riftbound.rbusers IS 'Usuarios registrados en la aplicacion';
COMMENT ON COLUMN riftbound.rbusers.id IS 'Identificador unico del usuario';
COMMENT ON COLUMN riftbound.rbusers.username IS 'Nombre de usuario unico';
COMMENT ON COLUMN riftbound.rbusers.email IS 'Correo electronico unico';
COMMENT ON COLUMN riftbound.rbusers.password_hash IS 'Hash de la contrasena';
COMMENT ON COLUMN riftbound.rbusers.created_at IS 'Fecha de creacion del usuario';

-- =============================================
-- TABLA: rbset (Sets de cartas)
-- Compatible con modelo app/models/set.py
-- =============================================
DROP TABLE IF EXISTS riftbound.rbset;

CREATE TABLE riftbound.rbset (
    rbset_id VARCHAR(20) PRIMARY KEY,
    rbset_name VARCHAR(200) NOT NULL,
    rbset_ncard SMALLINT,
    rbset_outdat DATE
);

-- Comentarios para rbset
COMMENT ON TABLE riftbound.rbset IS 'Sets deExpansion de cartas';
COMMENT ON COLUMN riftbound.rbset.rbset_id IS 'Identificador unico del set (codigo)';
COMMENT ON COLUMN riftbound.rbset.rbset_name IS 'Nombre completo del set';
COMMENT ON COLUMN riftbound.rbset.rbset_ncard IS 'Numero total de cartas en el set';
COMMENT ON COLUMN riftbound.rbset.rbset_outdat IS 'Fecha de obsolescencia del set';

-- =============================================
-- TABLA: rbcards (Cartas)
-- Compatible con modelo app/models/card.py
-- =============================================
DROP TABLE IF EXISTS riftbound.rbcards;

CREATE TABLE riftbound.rbcards (
    rbcar_rbset_id VARCHAR(20) NOT NULL REFERENCES riftbound.rbset(rbset_id),
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

-- Comentarios para rbcards
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

-- =============================================
-- TABLA: rbcollection (Colección de usuario)
-- Compatible con modelo app/models/collection.py
-- =============================================
DROP TABLE IF EXISTS riftbound.rbcollection;

CREATE TABLE riftbound.rbcollection (
    rbcol_rbset_id VARCHAR(20) NOT NULL,
    rbcol_rbcar_id VARCHAR(20) NOT NULL,
    rbcol_foil VARCHAR(1) DEFAULT 'N',
    rbcol_quantity VARCHAR(20) NOT NULL,
    rbcol_chadat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    rbcol_user VARCHAR(80),
    PRIMARY KEY (rbcol_rbset_id, rbcol_rbcar_id, rbcol_foil),
    CONSTRAINT fk_collection_card FOREIGN KEY (rbcol_rbset_id, rbcol_rbcar_id) 
        REFERENCES riftbound.rbcards(rbcar_rbset_id, rbcar_id),
    CONSTRAINT fk_collection_user FOREIGN KEY (rbcol_user) REFERENCES riftbound.rbusers(username)
);

CREATE INDEX idx_rbcollection_user ON riftbound.rbcollection (rbcol_user);
CREATE INDEX idx_rbcollection_set_card ON riftbound.rbcollection (rbcol_rbset_id, rbcol_rbcar_id);

-- Comentarios para rbcollection
COMMENT ON TABLE riftbound.rbcollection IS 'Coleccion personal de cada usuario';
COMMENT ON COLUMN riftbound.rbcollection.rbcol_rbset_id IS 'FK al set de la carta';
COMMENT ON COLUMN riftbound.rbcollection.rbcol_rbcar_id IS 'FK al ID de la carta';
COMMENT ON COLUMN riftbound.rbcollection.rbcol_foil IS 'Si la carta es foil (S/N)';
COMMENT ON COLUMN riftbound.rbcollection.rbcol_quantity IS 'Cantidad de copias de la carta';
COMMENT ON COLUMN riftbound.rbcollection.rbcol_chadat IS 'Fecha de ultimo cambio en la coleccion';
COMMENT ON COLUMN riftbound.rbcollection.rbcol_user IS 'FK al usuario propietario';

-- =============================================
-- TABLA: rbdecks (Mazos)
-- Compatible con modelo app/models/deck.py
-- =============================================
DROP TABLE IF EXISTS riftbound.rbdecks;

CREATE TABLE riftbound.rbdecks (
    id SERIAL PRIMARY KEY,
    rbdck_user VARCHAR(80) NOT NULL,
    rbdck_name VARCHAR(200) NOT NULL,
    rbdck_seq INTEGER DEFAULT 1,
    rbdck_snapshot TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    rbdck_decription TEXT,
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

-- Comentarios para rbdecks
COMMENT ON TABLE riftbound.rbdecks IS 'Mazos creados por usuarios';
COMMENT ON COLUMN riftbound.rbdecks.id IS 'Identificador unico autoincremental del deck';
COMMENT ON COLUMN riftbound.rbdecks.rbdck_user IS 'FK al usuario propietario del deck';
COMMENT ON COLUMN riftbound.rbdecks.rbdck_name IS 'Nombre del deck';
COMMENT ON COLUMN riftbound.rbdecks.rbdck_seq IS 'Secuencial para permitir multiples versiones del mismo deck';
COMMENT ON COLUMN riftbound.rbdecks.rbdck_snapshot IS 'Fecha/hora de creacion del deck (incluye hora, min, seg)';
COMMENT ON COLUMN riftbound.rbdecks.rbdck_decription IS 'Descripcion del deck';
COMMENT ON COLUMN riftbound.rbdecks.rbdck_mode IS 'Modo de juego (1v1, Commander, Team, Draft)';
COMMENT ON COLUMN riftbound.rbdecks.rbdck_format IS 'Formato del deck (Standard, Expanded, Classic)';
COMMENT ON COLUMN riftbound.rbdecks.rbdck_max_set IS 'Sets permitidos en el deck';
COMMENT ON COLUMN riftbound.rbdecks.rbdck_ncards IS 'Numero total de cartas en el deck';
COMMENT ON COLUMN riftbound.rbdecks.rbdck_orden IS 'Orden de visualizacion del deck';
COMMENT ON COLUMN riftbound.rbdecks.rbdck_cards IS 'Cartas del deck en formato JSON: {"main": [...], "sideboard": [...]}';

-- =============================================
-- TABLA: rbcardmarket (Precios de cartas)
-- Compatible con modelo app/models/market.py
-- =============================================
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

-- Comentarios para rbcardmarket
COMMENT ON TABLE riftbound.rbcardmarket IS 'Precios de cartas del mercado';
COMMENT ON COLUMN riftbound.rbcardmarket.rbcmk_snapshot IS 'Fecha/hora del precio';
COMMENT ON COLUMN riftbound.rbcardmarket.rbcmk_rbset_id IS 'FK al set de la carta';
COMMENT ON COLUMN riftbound.rbcardmarket.rbcmk_rbcar_id IS 'FK al ID de la carta';
COMMENT ON COLUMN riftbound.rbcardmarket.rbcmk_foil IS 'Si el precio es para version foil (S/N)';
COMMENT ON COLUMN riftbound.rbcardmarket.rbcmk_name IS 'Nombre de la carta';
COMMENT ON COLUMN riftbound.rbcardmarket.rbcmk_price IS 'Precio de la carta';