-- =============================================
-- DATOS DE EJEMPLO - RIFTBOUND MANAGER
-- Base de datos: postgres
-- Esquema: riftbound
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