-- =============================================
-- Migration 08: Ignored Products Table
-- =============================================
-- Adds the rbcm_ignored table for tracking products
-- explicitly ignored by the user in the mappings browser.
-- Identified by (idProduct, name) composite PK.
--
-- Usage:
--   psql -h <host> -U <user> -d <database> -f 08_ignored_products.sql
-- =============================================

CREATE TABLE IF NOT EXISTS riftbound.rbcm_ignored (
    rbig_id_product INT NOT NULL,
    rbig_name TEXT NOT NULL,
    rbig_ignored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (rbig_id_product, rbig_name)
);

CREATE INDEX IF NOT EXISTS idx_rbcm_ignored_id ON riftbound.rbcm_ignored(rbig_id_product);

COMMENT ON TABLE riftbound.rbcm_ignored IS 'Products explicitly ignored by users in the mappings browser. Identified by (idProduct, name) composite PK.';
COMMENT ON COLUMN riftbound.rbcm_ignored.rbig_id_product IS 'Cardmarket idProduct';
COMMENT ON COLUMN riftbound.rbcm_ignored.rbig_name IS 'Product name (part of composite PK to distinguish variants)';
COMMENT ON COLUMN riftbound.rbcm_ignored.rbig_ignored_at IS 'When the product was ignored';
