# Documentación de Instalación - Base de Datos
## Riftbound Manager

### Resumen

Este documento describe el orden de instalación de las migraciones de base de datos para el proyecto Riftbound Manager.

---

## Pre-requisitos

1. **PostgreSQL** instalado y corriendo
2. **Acceso** a la base de datos `postgres` con permisos de lectura/escritura
3. **Herramientas**: psql, pgAdmin, o cualquier cliente PostgreSQL

---

## Orden de Instalación

### Paso 1: Estructura de Tablas
**Archivo**: `01_create_tables.sql`

```bash
psql -U postgres -d postgres -f migrations/database/01_create_tables.sql
```

**Contenido**:
- Crea el esquema `riftbound` (si no existe)
- Crea todas las tablas del sistema con Foreign Keys:
  - `rbusers` - Usuarios registrados (campos: id, username, email, password_hash, created_at)
  - `rbset` - Sets de cartas
  - `rbcards` - Catálogo de cartas (FK → rbset)
  - `rbcollection` - Colección personal (FK → rbcards, rbusers)
  - `rbdecks` - Mazos (FK → rbusers)
  - `rbcardmarket` - Precios del mercado (FK → rbcards)
- Crea índices para optimización
- Añade comentarios a tablas y columnas

### Paso 2: Datos de Ejemplo (Opcional)
**Archivo**: `02_sample_data.sql`

```bash
psql -U postgres -d postgres -f migrations/database/02_sample_data.sql
```

---

## Estructura de Tablas (Nombres de campos)

### rbusers
```sql
CREATE TABLE riftbound.rbusers (
    id SERIAL PRIMARY KEY,
    username VARCHAR(80) NOT NULL UNIQUE,
    email VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(256),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### rbset
```sql
CREATE TABLE riftbound.rbset (
    rbset_id VARCHAR(20) PRIMARY KEY,
    rbset_name VARCHAR(200) NOT NULL,
    rbset_ncard SMALLINT,
    rbset_outdat DATE
);
```

### rbcards
```sql
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
```

### rbdecks
```sql
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
```

---

## Foreign Keys Definidas

| Tabla | Columna | Referencia | Descripción |
|-------|--------|-----------|-------------|
| rbcards | rbcar_rbset_id | → rbset(rbset_id) | FK a sets |
| rbcollection | (rbcol_rbset_id, rbcol_rbcar_id) | → rbcards | FK a cartas |
| rbcollection | rbcol_user | → rbusers(username) | FK a usuario |
| rbdecks | rbdck_user | → rbusers(username) | FK a usuario |
| rbcardmarket | (rbcmk_rbset_id, rbcmk_rbcar_id) | → rbcards | FK a cartas |

---

## ⚠️ Importante: Este script elimina las tablas anteriores

El script `01_create_tables.sql` contiene `DROP TABLE IF EXISTS` para cada tabla.

Esto significa que **cualquier dato existente se eliminará**.

Si tienes datos importantes:
1. Haz un respaldo antes de ejecutar
2. O modifica el script para no hacer DROP

---

## Verificar instalación

```sql
-- Ver tablas creadas
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'riftbound';

-- Ver estructura de rbusers
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'rbusers' AND table_schema = 'riftbound';
```

---

## Troubleshooting

### Error: "relation already exists"

Si las tablas ya existen y quieres recrear:

```sql
DROP TABLE IF EXISTS riftbound.rbdecks CASCADE;
DROP TABLE IF EXISTS riftbound.rbcollection CASCADE;
DROP TABLE IF EXISTS riftbound.rbcards CASCADE;
DROP TABLE IF EXISTS riftbound.rbset CASCADE;
DROP TABLE IF EXISTS riftbound.rbusers CASCADE;
DROP TABLE IF EXISTS riftbound.rbcardmarket CASCADE;
```

### Error: "permission denied"

Asegúrate de tener permisos:

```sql
GRANT ALL PRIVILEGES ON DATABASE postgres TO postgres;
GRANT ALL ON SCHEMA riftbound TO postgres;
```

---

## Archivos de Migración

```
migrations/
└── database/
    ├── 01_create_tables.sql    -- Estructura de base de datos
    ├── 02_sample_data.sql      -- Datos de ejemplo (opcional)
    └── README.md               -- Este documento
```