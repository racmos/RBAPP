-- Riftbound Database Setup Script
-- PostgreSQL Database Initialization

-- Create schema
CREATE SCHEMA IF NOT EXISTS riftbound;

-- =====================================================
-- TABLE: rbset (Card Sets/Expansions)
-- =====================================================
CREATE TABLE IF NOT EXISTS riftbound.rbset (
	rbset_id TEXT NOT NULL,
	rbset_name TEXT NOT NULL,
	rbset_ncard INT2 NULL,
	rbset_outdat DATE NULL,
	CONSTRAINT rbset_pk PRIMARY KEY (rbset_id)
);

COMMENT ON TABLE riftbound.rbset IS 'Tabla de expansiones';
COMMENT ON COLUMN riftbound.rbset.rbset_id IS 'ID de la expansión';
COMMENT ON COLUMN riftbound.rbset.rbset_name IS 'Nombre expansión';
COMMENT ON COLUMN riftbound.rbset.rbset_ncard IS 'Número de cartas que contiene la expansión';
COMMENT ON COLUMN riftbound.rbset.rbset_outdat IS 'Fecha de lanzamiento de la expansión';

ALTER TABLE riftbound.rbset OWNER TO postgres;
GRANT ALL ON TABLE riftbound.rbset TO postgres;

-- =====================================================
-- TABLE: rbcards (Individual Cards)
-- =====================================================
CREATE TABLE IF NOT EXISTS riftbound.rbcards (
	rbcar_rbset_id TEXT NOT NULL,
	rbcar_id TEXT NOT NULL,
	rbcar_name TEXT NOT NULL,
	rbcar_domain TEXT NULL,
	rbcar_type TEXT NULL,
	rbcar_tags TEXT NULL,
	rbcar_energy INT2 NULL,
	rbcar_power INT2 NULL,
	rbcar_might INT2 NULL,
	rbcar_ability TEXT NULL,
	rbcar_rarity TEXT NULL,
	rbcar_artist TEXT NULL,
	rbcar_banned TEXT DEFAULT 'N'::TEXT NULL,
	image_url TEXT NULL,
	CONSTRAINT rbcards_pk PRIMARY KEY (rbcar_rbset_id, rbcar_id)
);

COMMENT ON TABLE riftbound.rbcards IS 'Tabla de cartas';
COMMENT ON COLUMN riftbound.rbcards.rbcar_rbset_id IS 'ID de la expansión';
COMMENT ON COLUMN riftbound.rbcards.rbcar_id IS 'ID de la carta';
COMMENT ON COLUMN riftbound.rbcards.rbcar_name IS 'Nombre de la carta';
COMMENT ON COLUMN riftbound.rbcards.rbcar_domain IS 'Dominio o color: fury, calm, mind, body, chaos, order, colorless';
COMMENT ON COLUMN riftbound.rbcards.rbcar_type IS 'Tipo de carta: Spell, Unit,...';
COMMENT ON COLUMN riftbound.rbcards.rbcar_tags IS 'Región, nombre de único o temática (ej. Dragón)';
COMMENT ON COLUMN riftbound.rbcards.rbcar_energy IS 'Coste de energía';
COMMENT ON COLUMN riftbound.rbcards.rbcar_power IS 'Coste de poder';
COMMENT ON COLUMN riftbound.rbcards.rbcar_might IS 'Fuerza / Defensa';
COMMENT ON COLUMN riftbound.rbcards.rbcar_ability IS 'Habilidad en el cuadro de la carta';
COMMENT ON COLUMN riftbound.rbcards.rbcar_rarity IS 'Rareza: Común, infrecuente,...';
COMMENT ON COLUMN riftbound.rbcards.rbcar_artist IS 'Autor del dibujo de la carta';
COMMENT ON COLUMN riftbound.rbcards.rbcar_banned IS 'Si ha sido baneada para jugarse en competitivo, S o N';
COMMENT ON COLUMN riftbound.rbcards.image_url IS 'Enlace a la imagen';

ALTER TABLE riftbound.rbcards OWNER TO postgres;
GRANT ALL ON TABLE riftbound.rbcards TO postgres;

ALTER TABLE riftbound.rbcards ADD CONSTRAINT rbcards_rbset_fk_1 
    FOREIGN KEY (rbcar_rbset_id) REFERENCES riftbound.rbset(rbset_id) 
    ON DELETE CASCADE ON UPDATE CASCADE;

-- =====================================================
-- TABLE: rbusers (User Authentication)
-- =====================================================
CREATE TABLE IF NOT EXISTS riftbound.rbusers ( 
    id SERIAL4 NOT NULL, 
    username VARCHAR(64) NOT NULL, 
    email VARCHAR(120) NOT NULL, 
    password_hash VARCHAR(256) NOT NULL, 
    created_at TIMESTAMP DEFAULT NOW() NULL, 
    CONSTRAINT rbusers_email_key UNIQUE (email), 
    CONSTRAINT rbusers_pkey PRIMARY KEY (id), 
    CONSTRAINT rbusers_username_key UNIQUE (username)
);

COMMENT ON TABLE riftbound.rbusers IS 'Tabla de usuarios';

ALTER TABLE riftbound.rbusers OWNER TO postgres;
GRANT ALL ON TABLE riftbound.rbusers TO postgres;
GRANT ALL ON SEQUENCE riftbound.rbusers_id_seq TO postgres;

-- =====================================================
-- TABLE: rbcollection (User's Card Collection)
-- =====================================================
CREATE TABLE IF NOT EXISTS riftbound.rbcollection (
	rbcol_rbset_id TEXT NOT NULL,
	rbcol_rbcar_id TEXT NOT NULL,
	rbcol_foil TEXT DEFAULT 'N'::TEXT NOT NULL,
	rbcol_quantity TEXT NOT NULL,
	rbcol_chadat TIMESTAMP NOT NULL,
	rbcol_user VARCHAR(64) NULL,
	CONSTRAINT rbcollection_pk PRIMARY KEY (rbcol_rbset_id, rbcol_rbcar_id, rbcol_foil)
);

COMMENT ON TABLE riftbound.rbcollection IS 'Tabla de cartas en posesión';
COMMENT ON COLUMN riftbound.rbcollection.rbcol_rbset_id IS 'ID de la expansión';
COMMENT ON COLUMN riftbound.rbcollection.rbcol_rbcar_id IS 'ID de la carta';
COMMENT ON COLUMN riftbound.rbcollection.rbcol_foil IS 'Si es foil, S o N';
COMMENT ON COLUMN riftbound.rbcollection.rbcol_quantity IS 'Cantidad de cartas';
COMMENT ON COLUMN riftbound.rbcollection.rbcol_chadat IS 'Fecha del último cambio';
COMMENT ON COLUMN riftbound.rbcollection.rbcol_user IS 'Usuario propietario de la colección';

ALTER TABLE riftbound.rbcollection OWNER TO postgres;
GRANT ALL ON TABLE riftbound.rbcollection TO postgres;

ALTER TABLE riftbound.rbcollection ADD CONSTRAINT rbcollection_rbcar_fk_1 
    FOREIGN KEY (rbcol_rbset_id, rbcol_rbcar_id) 
    REFERENCES riftbound.rbcards(rbcar_rbset_id, rbcar_id) 
    ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE riftbound.rbcollection ADD CONSTRAINT rbcollection_user_fk_1 
    FOREIGN KEY (rbcol_user) REFERENCES riftbound.rbusers(username) 
    ON UPDATE CASCADE ON DELETE RESTRICT;

-- =====================================================
-- TABLE: rbcardmarket (Card Prices)
-- =====================================================
CREATE TABLE IF NOT EXISTS riftbound.rbcardmarket (
	rbcmk_snapshot TIMESTAMP DEFAULT NOW() NOT NULL,
	rbcmk_rbset_id TEXT NOT NULL,
	rbcmk_rbcar_id TEXT NOT NULL,
	rbcmk_name TEXT NOT NULL,
	rbcmk_foil TEXT DEFAULT 'N'::TEXT NOT NULL,
	rbcmk_price NUMERIC NOT NULL,
	CONSTRAINT rbcmk_pk PRIMARY KEY (rbcmk_snapshot, rbcmk_rbset_id, rbcmk_rbcar_id, rbcmk_foil)
);

COMMENT ON TABLE riftbound.rbcardmarket IS 'Tabla de precios de Cardmarket';
COMMENT ON COLUMN riftbound.rbcardmarket.rbcmk_snapshot IS 'Fecha de la foto de los precios extraídos';
COMMENT ON COLUMN riftbound.rbcardmarket.rbcmk_rbset_id IS 'ID de la expansión';
COMMENT ON COLUMN riftbound.rbcardmarket.rbcmk_rbcar_id IS 'ID de la carta';
COMMENT ON COLUMN riftbound.rbcardmarket.rbcmk_name IS 'Nombre de la carta';
COMMENT ON COLUMN riftbound.rbcardmarket.rbcmk_foil IS 'Si es foil, S o N';
COMMENT ON COLUMN riftbound.rbcardmarket.rbcmk_price IS 'Precio de la carta';

ALTER TABLE riftbound.rbcardmarket OWNER TO postgres;
GRANT ALL ON TABLE riftbound.rbcardmarket TO postgres;

ALTER TABLE riftbound.rbcardmarket ADD CONSTRAINT rbcmk_rbcar_fk_1 
    FOREIGN KEY (rbcmk_rbset_id, rbcmk_rbcar_id) 
    REFERENCES riftbound.rbcards(rbcar_rbset_id, rbcar_id) 
    ON DELETE CASCADE ON UPDATE CASCADE;

-- =====================================================
-- TABLE: rbdecks (User's Decks)
-- =====================================================
CREATE TABLE IF NOT EXISTS riftbound.rbdecks (
	rbdck_snapshot TIMESTAMP DEFAULT NOW() NOT NULL,
	rbdck_name TEXT NOT NULL,
	rbdck_decription TEXT NULL,
	rbdck_mode TEXT DEFAULT '1v1'::TEXT NOT NULL,
	rbdck_format TEXT DEFAULT 'Standard'::TEXT NOT NULL,
	rbdck_max_set TEXT NOT NULL,
	rbdck_rbset_id TEXT NOT NULL,
	rbdck_rbcar_id TEXT NOT NULL,
	rbdck_ncards NUMERIC DEFAULT 1 NOT NULL,
	rbdck_sideboard TEXT DEFAULT 'N'::TEXT NOT NULL,
	rbdck_user TEXT NOT NULL,
	rbdck_xcards NUMERIC NULL,
	CONSTRAINT rbdck_pk PRIMARY KEY (rbdck_snapshot, rbdck_rbset_id, rbdck_rbcar_id, rbdck_sideboard, rbdck_user)
);

COMMENT ON TABLE riftbound.rbdecks IS 'Tabla de mazos';
COMMENT ON COLUMN riftbound.rbdecks.rbdck_snapshot IS 'Fecha de guardado del deck';
COMMENT ON COLUMN riftbound.rbdecks.rbdck_name IS 'Nombre del mazo';
COMMENT ON COLUMN riftbound.rbdecks.rbdck_decription IS 'Descripción del mazo';
COMMENT ON COLUMN riftbound.rbdecks.rbdck_mode IS 'Modo de juego';
COMMENT ON COLUMN riftbound.rbdecks.rbdck_format IS 'Formato de juego';
COMMENT ON COLUMN riftbound.rbdecks.rbdck_max_set IS 'Set más reciente con el que esta formado el deck';
COMMENT ON COLUMN riftbound.rbdecks.rbdck_rbset_id IS 'ID de la expansión';
COMMENT ON COLUMN riftbound.rbdecks.rbdck_rbcar_id IS 'ID de la carta';
COMMENT ON COLUMN riftbound.rbdecks.rbdck_ncards IS 'Cantidad de cartas';
COMMENT ON COLUMN riftbound.rbdecks.rbdck_sideboard IS 'Si pertenece al banquillo';
COMMENT ON COLUMN riftbound.rbdecks.rbdck_user IS 'Propietario del deck';
COMMENT ON COLUMN riftbound.rbdecks.rbdck_xcards IS 'Cantidad de cartas faltantes';

ALTER TABLE riftbound.rbdecks OWNER TO postgres;
GRANT ALL ON TABLE riftbound.rbdecks TO postgres;

ALTER TABLE riftbound.rbdecks ADD CONSTRAINT rbdck_rbcar_fk_1 
    FOREIGN KEY (rbdck_rbset_id, rbdck_rbcar_id) 
    REFERENCES riftbound.rbcards(rbcar_rbset_id, rbcar_id) 
    ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE riftbound.rbdecks ADD CONSTRAINT rbdecks_user_fk_1 
    FOREIGN KEY (rbdck_user) REFERENCES riftbound.rbusers(username) 
    ON UPDATE CASCADE ON DELETE RESTRICT;

-- =====================================================
-- INDEXES for better performance
-- =====================================================
CREATE INDEX IF NOT EXISTS idx_rbcards_name ON riftbound.rbcards(rbcar_name);
CREATE INDEX IF NOT EXISTS idx_rbcards_domain ON riftbound.rbcards(rbcar_domain);
CREATE INDEX IF NOT EXISTS idx_rbcards_rarity ON riftbound.rbcards(rbcar_rarity);
CREATE INDEX IF NOT EXISTS idx_rbcollection_set ON riftbound.rbcollection(rbcol_rbset_id);
CREATE INDEX IF NOT EXISTS idx_rbcollection_user ON riftbound.rbcollection(rbcol_user);
CREATE INDEX IF NOT EXISTS idx_rbdecks_user ON riftbound.rbdecks(rbdck_user);
CREATE INDEX IF NOT EXISTS idx_rbdecks_name ON riftbound.rbdecks(rbdck_name);
CREATE INDEX IF NOT EXISTS idx_rbcardmarket_snapshot ON riftbound.rbcardmarket(rbcmk_snapshot);

-- =====================================================
-- SAMPLE DATA (Optional)
-- =====================================================

-- Sample Sets
INSERT INTO riftbound.rbset (rbset_id, rbset_name, rbset_ncard, rbset_outdat) VALUES
('OGN', 'Origins', 300, '2024-01-15'),
('OGS', 'Origins Starter', 150, '2024-01-15')
ON CONFLICT (rbset_id) DO NOTHING;

-- Sample Cards
INSERT INTO riftbound.rbcards (
    rbcar_rbset_id, rbcar_id, rbcar_name, rbcar_domain, rbcar_type, 
    rbcar_rarity, rbcar_energy, rbcar_power, rbcar_might, rbcar_banned
) VALUES
('OGN', '001', 'Test Card 1', 'fury', 'Unit', 'Common', 3, 2, 3, 'N'),
('OGN', '002', 'Test Card 2', 'calm', 'Spell', 'Uncommon', 2, 1, 0, 'N'),
('OGS', '001', 'Starter Card 1', 'mind', 'Unit', 'Common', 1, 1, 1, 'N')
ON CONFLICT (rbcar_rbset_id, rbcar_id) DO NOTHING;

-- =====================================================
-- DISPLAY TABLE INFORMATION
-- =====================================================
SELECT 
    'Users' as table_name, 
    COUNT(*) as record_count 
FROM riftbound.rbusers
UNION ALL
SELECT 
    'Sets' as table_name, 
    COUNT(*) as record_count 
FROM riftbound.rbset
UNION ALL
SELECT 
    'Cards' as table_name, 
    COUNT(*) as record_count 
FROM riftbound.rbcards
UNION ALL
SELECT 
    'Collection' as table_name, 
    COUNT(*) as record_count 
FROM riftbound.rbcollection
UNION ALL
SELECT 
    'Card Market' as table_name, 
    COUNT(*) as record_count 
FROM riftbound.rbcardmarket
UNION ALL
SELECT 
    'Decks' as table_name, 
    COUNT(*) as record_count 
FROM riftbound.rbdecks;
