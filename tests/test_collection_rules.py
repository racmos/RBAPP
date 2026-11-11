"""F3-a S5: the collection rules of the JSON API."""
from types import SimpleNamespace

import pytest

from app.services.collection_rules import DEFAULT_PLAYSET_SIZE, kept_copies, playset_size


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
