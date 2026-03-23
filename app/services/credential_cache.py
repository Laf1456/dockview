"""
Credential Cache — in-memory override store for manual credentials.
"""

_cache: dict = {}


def get(db_id: str) -> dict:
    return _cache.get(db_id, {})


def set_creds(db_id: str, creds: dict):
    _cache[db_id] = creds


def clear(db_id: str):
    _cache.pop(db_id, None)
