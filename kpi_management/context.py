"""Server-only action capability; never trust flags supplied in document JSON."""

from contextlib import contextmanager
from contextvars import ContextVar

_action = ContextVar("kpi_management_action", default=None)


@contextmanager
def action(kind, name=None):
    token = _action.set((kind, name))
    try:
        yield
    finally:
        _action.reset(token)


def current(doc=None):
    value = _action.get()
    if not value or (value[1] is not None and doc is not None and value[1] != doc.name):
        return None
    return value[0]

