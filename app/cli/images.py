"""`flask images ...`: card images in CARD_IMAGES_DIR (M-d S7, D-Md-3).

`import-legacy` copies the images that used to live in the code tree into the
data directory. It copies, never moves; an existing file is never overwritten,
so running it again copies nothing.

`prune-orphans` (F13-h S7) lists, then deletes, the image files of CARD_IMAGES_DIR and
PRODUCT_IMAGES_DIR that no card or product row names (`--dry-run` only lists). It is run by
hand, never by a timer: a file kept for an Undo still open in a browser is an orphan too.
"""
import os

import click
from flask import current_app
from flask.cli import AppGroup

from app.services.card_images import import_legacy as copy_legacy
from app.services.image_upload import orphans

images_cli = AppGroup('images', help='Card and product images (CARD_IMAGES_DIR, '
                                     'PRODUCT_IMAGES_DIR).')


@images_cli.command('import-legacy')
@click.option('--source', type=click.Path(exists=True, file_okay=False),
              help='Folder holding <folder>/<file>; default app/static/images/cards.')
def import_legacy(source):
    """Copy every <folder>/<file> image of SOURCE into CARD_IMAGES_DIR."""
    # Read from disk: the app has no static route (the Jinja web is gone).
    source = source or os.path.join(current_app.root_path, 'static', 'images', 'cards')
    copied, skipped, ignored = copy_legacy(source)
    click.echo(f'Copied {copied}, skipped {skipped} existing, ignored {ignored}.')


@images_cli.command('prune-orphans')
@click.option('--dry-run', is_flag=True, help='List the orphan files, delete nothing.')
def prune_orphans(dry_run):
    """Delete the card and product image files no row references."""
    found = orphans()
    deleted = 0
    for label, path in found:
        click.echo(label)
        if not dry_run:
            try:
                os.remove(path)
            except OSError as exc:
                click.echo(f'Could not delete {label}: {exc.strerror}', err=True)
                continue
            deleted += 1
    if dry_run:
        click.echo(f'{len(found)} orphan files (dry run, nothing deleted).')
    else:
        click.echo(f'Deleted {deleted} orphan files.')
