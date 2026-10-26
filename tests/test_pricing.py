"""F2-b S5 (AC2): `resolve_price` keeps the PRC-1/PRC-2 behaviour, and the new
`resolve_price_with_source` reports which column won.

PRC-1/PRC-2 (openspec/specs/price-resolution/spec.md) predate this unit; the
old `tests/test_pricing.py` was removed by M-a, so the characterization table
below re-creates that guard in its smallest form (test policy).
"""
import pytest

from app.models.cardmarket import RbcmPrice
from app.services import pricing


def _row(**values):
    columns = dict(avg7=None, avg7_foil=None, low=None, low_foil=None)
    columns.update(values)
    return RbcmPrice(**{f'rbprc_{name}': value for name, value in columns.items()})


# --- PRC-1 fallback chain (characterization of the current implementation) ---

@pytest.mark.parametrize('kwargs, expected', [
    ({}, None),                                             # no row at all
    ({'row': _row()}, None),                                # all four NULL
    ({'row': _row(avg7=0, avg7_foil=0, low=0, low_foil=0)}, None),  # all zero
    ({'row': _row(avg7_foil=5.0, avg7=3.0), 'rarity': 'Rare'}, 5.0),
    ({'row': _row(low_foil=1.2, low=1.0), 'rarity': 'epic'}, 1.2),
    ({'row': _row(low=1.0), 'rarity': 'epic'}, 1.0),
    ({'row': _row(low=0.5), 'rarity': 'SHOWCASE'}, 0.5),
    ({'row': _row(avg7=0.1, avg7_foil=0.9), 'rarity': 'common'}, 0.1),
    ({'row': _row(low=0.2, low_foil=0.8), 'rarity': 'uncommon'}, 0.2),
    ({'row': _row(avg7_foil=0.9, avg7=0.1), 'rarity': 'common', 'foil': 'S'}, 0.9),
    ({'row': _row(avg7=1.5), 'rarity': None}, 1.5),
    ({'row': _row(avg7=1.5), 'rarity': ''}, 1.5),
    ({'row': _row(avg7_foil=2.0)}, 2.0),   # common chain tries the foil average second
    ({'row': _row(avg7_foil=2.0), 'foil': 'S'}, 2.0),
    ({'row': _row(low=0)}, None),           # 0 counts as missing
])
def test_resolve_price_fallback_chain(kwargs, expected):
    kwargs.setdefault('rarity', 'common')
    kwargs.setdefault('foil', 'N')
    assert pricing.resolve_price(kwargs.pop('row', None), **kwargs) == expected


def test_resolve_price_returns_float():
    assert pricing.resolve_price(_row(avg7=1), rarity='common', foil='N') == 1.0
    assert isinstance(pricing.resolve_price(_row(avg7=1), rarity='common', foil='N'), float)


# --- resolve_price_with_source (new in F2-b) ----------------------------------

@pytest.mark.parametrize('kwargs, expected', [
    ({'row': None, 'rarity': 'common', 'foil': 'N'}, (None, None)),
    ({'row': _row(), 'rarity': 'common', 'foil': 'N'}, (None, None)),
    ({'row': _row(avg7_foil=5.0, avg7=3.0), 'rarity': 'Rare', 'foil': 'N'},
     (5.0, 'avg7_foil')),
    ({'row': _row(avg7_foil=5.0, avg7=3.0), 'rarity': 'common', 'foil': 'N'},
     (3.0, 'avg7')),
    ({'row': _row(avg7=0.1, avg7_foil=0.9), 'rarity': 'common', 'foil': 'S'},
     (0.9, 'avg7_foil')),
    ({'row': _row(low=0.5), 'rarity': 'showcase', 'foil': 'N'}, (0.5, 'low')),
    ({'row': _row(low_foil=1.2, low=1.0), 'rarity': 'epic', 'foil': 'N'},
     (1.2, 'low_foil')),
    ({'row': _row(avg7=1.0), 'rarity': None, 'foil': 'N'}, (1.0, 'avg7')),
])
def test_resolve_price_with_source(kwargs, expected):
    assert pricing.resolve_price_with_source(**kwargs) == expected


def test_resolve_price_delegates_to_with_source():
    row = _row(avg7_foil=5.0, avg7=3.0)
    assert pricing.resolve_price(row, rarity='Rare', foil='N') == \
        pricing.resolve_price_with_source(row, rarity='Rare', foil='N')[0]
