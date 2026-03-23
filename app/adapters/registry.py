"""
Adapter Registry — maps DB types to adapter classes.
"""

from app.models import DatabaseType

_registry: dict[str, type] = {}


def register(db_type: DatabaseType):
    """Decorator to register an adapter."""
    def decorator(cls):
        _registry[db_type.value] = cls
        return cls
    return decorator


class AdapterRegistry:
    @staticmethod
    def get(db_type: DatabaseType):
        return _registry.get(db_type.value)

    @staticmethod
    def all():
        return dict(_registry)


# Import adapters to trigger registration
from app.adapters import postgres, mysql, mongo, redis  # noqa: E402, F401
