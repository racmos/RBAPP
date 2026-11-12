"""`price_alerts`: the daily wishlist price alerts (F4-g-2).

Queued by `daily_prices` when it succeeds, after `value_snapshot` and `products_refresh`
(and by hand with `flask jobs enqueue price_alerts`). It raises one alert per user, card
target and price date for the wishlist lines whose max price was reached on the latest
Cardmarket price load (`app/services/wishlist_alerts.py`); a second run on the same load
creates nothing.
"""
from app.jobs.registry import JobFailed, JobKind, register
from app.services import wishlist_alerts

NAME = 'price_alerts'


def run(params: dict) -> dict:
    if params:
        raise JobFailed(f'{NAME} takes no params')
    try:
        return wishlist_alerts.raise_alerts()
    except wishlist_alerts.NoPrices as exc:
        raise JobFailed(f'{NAME}: {exc}') from None


register(JobKind(NAME, run, timeout_seconds=900))
