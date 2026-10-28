"""Collection rules shared by the Jinja routes and the JSON API (F3-a S5).

Pure functions plus one helper that applies the legacy rule to a row. Nothing
here touches the request or commits.
"""

DEFAULT_PLAYSET_SIZE = 3


def legacy_sell_qty(qty: int, playset: int | None, selling: str) -> int:
    """Copies for sale under the old Jinja rules (the rule of migration 0014).

    With a playset set the surplus over it is for sale, whatever the flag says;
    without one the whole row is for sale when `selling` is 'Y'."""
    if playset is not None:
        return max(0, qty - playset)
    return qty if selling == 'Y' else 0


def kept_copies(lines) -> int:
    """Copies not for sale in `lines` (collection rows): the sum of quantity - sell_qty."""
    return sum(line.rbcol_quantity - line.rbcol_sell_qty for line in lines)


def playset_size(prefs) -> int:
    """The user's playset size: `rbprf_playset_size` of their preferences row, 3 when
    there is no row or no value."""
    size = getattr(prefs, 'rbprf_playset_size', None)
    return DEFAULT_PLAYSET_SIZE if size is None else size


def sync_legacy_sell_qty(col) -> None:
    """Set `col.rbcol_sell_qty` from its quantity, playset and selling (S6). The caller
    commits, in the same transaction as the change that made the count stale."""
    col.rbcol_sell_qty = legacy_sell_qty(col.rbcol_quantity, col.rbcol_playset, col.rbcol_selling)
