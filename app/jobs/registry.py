"""Job kinds the runner knows (F4-a S2).

A kind is a name, a handler and a timeout. The handler is
`handler(params: dict) -> dict`; the returned dict is stored in `rbjob_result`.
A handler raises `JobFailed(message)` for an expected failure: the runner
records the message as it is, without the exception class.
A kind must also be allowed by the `ck_rbjobs_kind` CHECK (`app.models.job`),
so a unit that registers one extends that CHECK with its own migration.
"""
from dataclasses import dataclass
from typing import Callable

Handler = Callable[[dict], dict]


@dataclass(frozen=True)
class JobKind:
    name: str
    handler: Handler
    timeout_seconds: int


class JobFailed(Exception):
    """An expected failure of a handler; its first line is the job message."""


_KINDS: dict[str, JobKind] = {}


def register(kind: JobKind) -> None:
    """Add `kind`; a name registered twice raises ValueError."""
    if kind.name in _KINDS:
        raise ValueError(f"Job kind '{kind.name}' is already registered")
    _KINDS[kind.name] = kind


def get(name: str) -> JobKind | None:
    return _KINDS.get(name)


def names() -> list[str]:
    return sorted(_KINDS)
