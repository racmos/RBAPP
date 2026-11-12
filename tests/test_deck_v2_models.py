"""F5-c S1, S2 (AC2): `RbDeckHead` / `RbDeckVersion` declare the constraints of migration
`0025_decks_v2` (name unique per user, mode and visibility domains, slug unique, seq unique per
deck) and default to a private deck."""
from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import RbDeckHead, RbDeckVersion

WHEN = datetime(2030, 1, 1, 12, 0)


def head(user, name='Azir', **kw):
    return RbDeckHead(rbdkh_user_id=user.id, rbdkh_name=name, rbdkh_mode=kw.pop('mode', '1v1'),
                      rbdkh_created_at=WHEN, rbdkh_updated_at=WHEN, **kw)


def version(deck, seq=1, **kw):
    return RbDeckVersion(rbdkv_deck_id=deck.rbdkh_id, rbdkv_seq=seq,
                         rbdkv_content={'v': 2}, rbdkv_created_at=WHEN, **kw)


def _refused(*objects):
    db.session.add_all(objects)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_a_deck_defaults_to_private_without_slug(app, make_user):
    ana = make_user('ana')
    deck = head(ana)
    db.session.add(deck)
    db.session.commit()
    db.session.add(version(deck))
    db.session.commit()
    assert (deck.rbdkh_visibility, deck.rbdkh_share_slug,
            deck.rbdkh_current_version_id) == ('private', None, None)
    assert RbDeckVersion.query.one().rbdkv_content == {'v': 2}


def test_the_name_is_unique_per_user(app, make_user):
    ana, bo = make_user('ana'), make_user('bo')
    db.session.add_all([head(ana), head(bo)])
    db.session.commit()
    _refused(head(ana))
    assert RbDeckHead.query.count() == 2


@pytest.mark.parametrize('field, value', [('mode', '3v3'), ('mode', 'Standard'),
                                          ('rbdkh_visibility', 'shared'),
                                          ('rbdkh_visibility', 'PUBLIC')])
def test_mode_and_visibility_have_closed_domains(app, make_user, field, value):
    _refused(head(make_user('ana'), **{field: value}))
    assert RbDeckHead.query.count() == 0


def test_the_share_slug_is_unique_and_optional(app, make_user):
    ana = make_user('ana')
    db.session.add_all([head(ana, 'A', rbdkh_share_slug='s' * 22), head(ana, 'B'),
                        head(ana, 'C', rbdkh_visibility='public')])
    db.session.commit()
    _refused(head(ana, 'D', rbdkh_share_slug='s' * 22))
    assert RbDeckHead.query.count() == 3


def test_the_seq_is_unique_per_deck(app, make_user):
    ana = make_user('ana')
    a, b = head(ana, 'A'), head(ana, 'B')
    db.session.add_all([a, b])
    db.session.commit()
    db.session.add_all([version(a, 1), version(a, 2), version(b, 1)])
    db.session.commit()
    _refused(version(a, 2))
    _refused(version(a, 0))
    assert RbDeckVersion.query.count() == 3
