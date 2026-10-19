"""table and column COMMENTs the dev database already had

Found by `flask db check` after the 0001 stamp (task 2.34): the dev database
carries COMMENTs on 8 tables (and their columns) that neither the models nor
0001 knew, so autogenerate kept proposing `modify_comment` / `remove_table_comment`.
The text below is copied from the dev catalog (structural metadata only) and
the models now declare the same text, so `flask db check` is clean everywhere.

PostgreSQL only: SQLite has no comments, the revision is a no-op there. On
dev the comments are already present and COMMENT ON simply sets the same text
again (idempotent). On a fresh database 0001..0004 create no comments, this
revision adds them, and downgrade removes them again.

Revision ID: 0004a_schema_comments
Revises: 0004_user_admin_flags
Create Date: 2026-10-19

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0004a_schema_comments'
down_revision = '0004_user_admin_flags'
branch_labels = None
depends_on = None

SCHEMA = 'riftbound'

# {table: {'table': comment or None, 'columns': {column: comment}}}
# tests/test_migrations.py pins this against the comments declared on the models.
COMMENTS = {
    'rbset': {
        'table': 'Tabla de expansiones',
        'columns': {
            'rbset_id': 'ID de la expansión',
            'rbset_name': 'Nombre expansión',
            'rbset_ncard': 'Número de cartas que contiene la expansión',
            'rbset_outdat': 'Fecha de lanzamiento de la expansión',
        },
    },
    'rbcards': {
        'table': 'Tabla de cartas',
        'columns': {
            'rbcar_rbset_id': 'ID de la expansión',
            'rbcar_id': 'ID de la carta',
            'rbcar_name': 'Nombre de la carta',
            'rbcar_domain': 'Dominio o color: fury, calm, mind, body, chaos, order, colorless',
            'rbcar_type': 'Tipo de carta: Spell, Unit,...',
            'rbcar_tags': 'Región, nombre de único o temática (ej. Dragón)',
            'rbcar_energy': 'Coste de energía',
            'rbcar_power': 'Coste de poder',
            'rbcar_might': 'Fuerza / Defensa',
            'rbcar_ability': 'Habilidad en el cuadro de la carta',
            'rbcar_rarity': 'Rareza: Común, infrecuente,...',
            'rbcar_artist': 'Autor del dibujo de la carta',
            'rbcar_banned': 'Si ha sido baneada para jugarse en competitivo, S o N',
            'image_url': 'Enlace a la imagen',
            'image': 'Nombre del archivo de la imagen',
        },
    },
    'rbcollection': {
        'table': 'Tabla de cartas en posesión',
        'columns': {
            'rbcol_rbset_id': 'ID de la expansión',
            'rbcol_rbcar_id': 'ID de la carta',
            'rbcol_foil': 'Si es foil, S o N',
            'rbcol_quantity': 'Cantidad de cartas',
            'rbcol_chadat': 'Fecha del último cambio',
            'rbcol_user': 'Usuario de la colección',
            'rbcol_selling': 'Indica si la carta está a la venta (Y/N)',
            'rbcol_playset': 'Nº de copias reservadas para playset (1, 2 o 3)',
            'rbcol_sell_price': 'Precio de venta unitario sobre el sobrante (quantity - playset)',
            'rbcol_condition': 'Estado de conservación (MT, NM, EX, GD, LP, PL, PO)',
            'rbcol_language': 'Idioma de la carta (English, Chinese, Spanish, ...)',
            'rbcol_id': 'PK sintética. Permite varias filas con la misma (set, card, foil, user) que difieran en condición, idioma o precio de venta.',
        },
    },
    'rbcardmarket': {
        'table': 'Tabla de precios de Cardmarket',
        'columns': {
            'rbcmk_snapshot': 'Fecha de la foto de los precios extraídos',
            'rbcmk_rbset_id': 'ID de la expansión',
            'rbcmk_rbcar_id': 'ID de la carta',
            'rbcmk_name': 'Nombre de la carta',
            'rbcmk_foil': 'Si es foil, S o N',
            'rbcmk_price': 'Precio de la carta',
        },
    },
    'rbcm_expansions': {
        'table': None,
        'columns': {
            'rbexp_rbset_id': 'FK blanda (sin constraint) al set interno riftbound.rbset.rbset_id. NULL = expansión de Cardmarket sin mapear todavía al catálogo de la app.',
        },
    },
    'rbcm_ignored': {
        'table': 'Products explicitly ignored by users in the mappings browser. Identified by (idProduct, name) composite PK.',
        'columns': {
            'rbig_id_product': 'Cardmarket idProduct',
            'rbig_name': 'Product name (part of composite PK to distinguish variants)',
            'rbig_ignored_at': 'When the product was ignored',
        },
    },
    'rbcm_price': {
        'table': None,
        'columns': {
            'rbprc_low_ex': 'Precio minimo ex+ (excluye foil)',
        },
    },
    'rbcm_product_card_map': {
        'table': None,
        'columns': {
            'rbpcm_foil': 'N=normal, S=foil, NULL=no aplica (rare/epic) o mapping legacy',
        },
    },
}


def _supports_comments():
    return op.get_context().dialect.name == 'postgresql'


def upgrade():
    if not _supports_comments():
        return
    for table, spec in COMMENTS.items():
        if spec['table']:
            op.create_table_comment(table, spec['table'], schema=SCHEMA)
        for column, text in spec['columns'].items():
            op.alter_column(table, column, schema=SCHEMA,
                            existing_type=sa.Text(), comment=text)


def downgrade():
    if not _supports_comments():
        return
    for table, spec in COMMENTS.items():
        if spec['table']:
            op.drop_table_comment(table, schema=SCHEMA)
        for column in spec['columns']:
            op.alter_column(table, column, schema=SCHEMA,
                            existing_type=sa.Text(), comment=None)
