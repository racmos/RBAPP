"""`flask images ...`: card images in CARD_IMAGES_DIR (M-d S7, D-Md-3).

`import-legacy` copies the images that used to live in the code tree into the
data directory. It copies, never moves; an existing file is never overwritten,
so running it again copies nothing.
"""
import os

import click
from flask import current_app
from flask.cli import AppGroup

from app.services.card_images import import_legacy as copy_legacy

images_cli = AppGroup('images', help='Card images in CARD_IMAGES_DIR.')


@images_cli.command('import-legacy')
@click.option('--source', type=click.Path(exists=True, file_okay=False),
              help='Folder holding <folder>/<file>; default <app static>/images/cards.')
def import_legacy(source):
    """Copy every <folder>/<file> image of SOURCE into CARD_IMAGES_DIR."""
    source = source or os.path.join(current_app.static_folder, 'images', 'cards')
    copied, skipped, ignored = copy_legacy(source)
    click.echo(f'Copied {copied}, skipped {skipped} existing, ignored {ignored}.')
