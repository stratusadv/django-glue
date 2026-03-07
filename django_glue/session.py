from __future__ import annotations

from time import time
from typing import Sequence, TYPE_CHECKING

from django.http import HttpRequest

from django_glue import settings, GlueAccess
from django_glue.exceptions import GlueProxyNotFoundError

if TYPE_CHECKING:
    from django_glue.proxies.proxy import BaseGlueProxy


class GlueSession:
    """
        A proxy class for the django session that exposes methods to register
        glue proxies to the session, set and renew their expiration times, and
        purge proxies that have expired from the session.
    """
    def __init__(self, request: HttpRequest):
        self.request = request

        self.proxy_registry = request.session.setdefault(
            settings.DJANGO_GLUE_SESSION_PROXY_KEY,
            dict()
        )

        self.keep_live_registry = request.session.setdefault(
            settings.DJANGO_GLUE_SESSION_KEEP_LIVE_KEY,
            dict()
        )

    @staticmethod
    def _get_next_expire_time() -> float:
        return time() + settings.DJANGO_GLUE_KEEP_LIVE_INTERVAL_TIME_SECONDS

    def _set_modified(self) -> None:
        self.request.session.modified = True

    def _proxy_is_expired(self, proxy_name):
        return time() > self.keep_live_registry[proxy_name]

    def get_proxy_access(self, unique_name: str) -> GlueAccess:
        access = self.proxy_registry.get(unique_name, None)
        if access is None:
            raise GlueProxyNotFoundError(unique_name)

        return access

    def register_proxy(self, proxy: BaseGlueProxy) -> None:
        self.proxy_registry[proxy.unique_name] = proxy.access

        self.keep_live_registry.setdefault(
            proxy.unique_name,
            self._get_next_expire_time()
        )

        self._set_modified()

    def purge_expired_proxies(self) -> None:
        proxy_names_to_purge = [
            proxy_name
            for proxy_name
            in self.keep_live_registry.keys()
            if self._proxy_is_expired(proxy_name)
        ]

        for proxy_name in proxy_names_to_purge:
            self.keep_live_registry.pop(proxy_name)
            self.proxy_registry.pop(proxy_name)

        self._set_modified()

    def renew_proxies(self, proxy_names: Sequence[str]) -> None:
        for proxy_name in proxy_names:
            if proxy_name in self.keep_live_registry:
                self.keep_live_registry[proxy_name] = self._get_next_expire_time()

        self._set_modified()