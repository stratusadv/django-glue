from __future__ import annotations

import hashlib

from functools import lru_cache
from pathlib import Path

from django.apps import apps
from django.contrib.staticfiles import finders

from django_glue import constants

BUNDLE_STATIC_PATH = 'django_glue/js/django_glue.js'


def asset_version() -> str:
    """Return the cache-busting version for the client bundle."""
    if not apps.is_installed('django.contrib.staticfiles'):
        return constants.__VERSION__

    path = finders.find(BUNDLE_STATIC_PATH)

    if not path:
        return constants.__VERSION__

    return _hashed_version(path, Path(path).stat().st_mtime_ns)


@lru_cache(maxsize=8)
def _hashed_version(path: str, mtime_ns: int) -> str:
    digest = hashlib.sha1(Path(path).read_bytes()).hexdigest()[:8]  # noqa: S324
    return f'{constants.__VERSION__}.{digest}'
