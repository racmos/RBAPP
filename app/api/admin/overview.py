"""GET /admin/overview: the first counters of the admin area (F13-R25, S3).

Four COUNTs, at most four statements. F13-e adds a `riot` block; clients
ignore unknown keys.
"""
from sqlalchemy import func, or_

from app import db
from app.api.admin import api_admin
from app.api.responses import ok
from app.models.card import RbCard
from app.models.set import RbSet


@api_admin.get('/overview')
def overview():
    sets = db.session.scalar(db.select(func.count()).select_from(RbSet))
    sets_without_date = db.session.scalar(
        db.select(func.count()).select_from(RbSet).where(RbSet.rbset_outdat.is_(None)))
    cards = db.session.scalar(db.select(func.count()).select_from(RbCard))
    cards_without_image = db.session.scalar(
        db.select(func.count()).select_from(RbCard)
        .where(or_(RbCard.image.is_(None), RbCard.image == '')))
    return ok({'catalog': {
        'sets': sets,
        'sets_without_release_date': sets_without_date,
        'cards': cards,
        'cards_without_image': cards_without_image,
    }})
