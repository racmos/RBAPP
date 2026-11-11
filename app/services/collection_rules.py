"""Collection rules of the JSON API (F3-a S5).

Pure functions. Nothing here touches the request or commits.
"""

DEFAULT_PLAYSET_SIZE = 3


def kept_copies(lines) -> int:
    """Copies not for sale in `lines` (collection rows): the sum of quantity - sell_qty."""
    return sum(line.rbcol_quantity - line.rbcol_sell_qty for line in lines)


def playset_size(prefs) -> int:
    """The user's playset size: `rbprf_playset_size` of their preferences row, 3 when
    there is no row or no value."""
    size = getattr(prefs, 'rbprf_playset_size', None)
    return DEFAULT_PLAYSET_SIZE if size is None else size
