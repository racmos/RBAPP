"""F3-a S5: the collection rules shared by the legacy routes and the new API."""
from types import SimpleNamespace

import pytest

from app.services.collection_rules import (DEFAULT_PLAYSET_SIZE, kept_copies, legacy_sell_qty,
                                           playset_size)


@pytest.mark.parametrize('qty, playset, selling, expected', [
    (5, 3, 'Y', 2),     # surplus over the playset
    (5, 3, 'N', 2),     # a playset decides, whatever the flag says
    (2, 3, 'Y', 0),     # never negative
    (3, 3, 'Y', 0),
    (4, 1, 'N', 3),
    (4, None, 'Y', 4),  # no playset: all of it, when for sale
    (4, None, 'N', 0),
    (1, None, 'Y', 1),
])
def test_legacy_sell_qty(qty, playset, selling, expected):
    assert legacy_sell_qty(qty, playset, selling) == expected


def line(quantity, sell_qty):
    return SimpleNamespace(rbcol_quantity=quantity, rbcol_sell_qty=sell_qty)


def test_kept_copies_is_quantity_minus_copies_to_sell():
    assert kept_copies([line(5, 2), line(3, 0), line(2, 2)]) == 6


def test_kept_copies_of_nothing_is_zero():
    assert kept_copies([]) == 0


def test_playset_size_defaults_to_three():
    assert DEFAULT_PLAYSET_SIZE == 3
    assert playset_size(None) == 3
    assert playset_size(SimpleNamespace(rbprf_playset_size=None)) == 3


@pytest.mark.parametrize('size', [1, 2, 4, 9])
def test_playset_size_reads_the_preference(size):
    assert playset_size(SimpleNamespace(rbprf_playset_size=size)) == size
