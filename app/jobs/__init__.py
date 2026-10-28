"""Background job kinds (F4-a). The single import point: importing this package
registers every kind, and `create_app` imports it once.

Add a kind: a module here that calls `registry.register(...)`, imported below,
plus a migration that extends `ck_rbjobs_kind`.
"""
from app.jobs import daily_prices  # noqa: F401  (registers 'daily_prices')
from app.jobs import riot_sync  # noqa: F401  (registers 'riot_sync')
from app.jobs import heartbeat  # noqa: F401  (registers 'heartbeat')
from app.jobs import value_snapshot  # noqa: F401  (registers 'value_snapshot')
