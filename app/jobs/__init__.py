"""Background job kinds (F4-a). The single import point: importing this package
registers every kind, and `create_app` imports it once.

Add a kind: a module here that calls `registry.register(...)`, imported below,
plus a migration that extends `ck_rbjobs_kind`.
"""
from app.jobs import heartbeat  # noqa: F401  (registers 'heartbeat')
