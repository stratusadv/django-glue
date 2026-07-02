from __future__ import annotations

import hashlib
import hmac
import json
from time import time
from typing import TYPE_CHECKING, Sequence

from django.conf import settings as django_settings

from django_glue import settings
from django_glue.exceptions import GlueProxyNotFoundError, GlueContextDataTamperingError

if TYPE_CHECKING:
    from django.http import HttpRequest
    from django_glue.access.access import GlueAccess
    from django_glue.proxies.proxy import BaseGlueProxy


def _compute_context_signature(context_data: dict) -> str:
    """
    Compute a cryptographic signature for context_data.

    Uses HMAC-SHA256 with Django's SECRET_KEY to ensure the signature
    cannot be forged without knowing the secret.
    """
    # Serialize to JSON with sorted keys for consistent hashing
    data_str = json.dumps(context_data, sort_keys=True, default=str)
    secret = django_settings.SECRET_KEY.encode('utf-8')
    return hmac.new(secret, data_str.encode('utf-8'), hashlib.sha256).hexdigest()


class GlueSession:
    """
    A proxy class for the django session that exposes methods to register
    glue proxies to the session, set and renew their expiration times, and
    purge proxies that have expired from the session.
    """

    def __init__(self, request: HttpRequest) -> None:
        self.request = request

        self.proxy_registry = request.session.setdefault(settings.DJANGO_GLUE_SESSION_PROXY_KEY, {})

        self.keep_live_registry = request.session.setdefault(
            settings.DJANGO_GLUE_SESSION_KEEP_LIVE_KEY, {}
        )

    @staticmethod
    def _get_next_expire_time() -> float:
        return (
            time() + settings.DJANGO_GLUE_KEEP_LIVE_INTERVAL_TIME_SECONDS + 60
        )  # Buffer for Request Timeouts

    def _set_modified(self) -> None:
        self.request.session.modified = True

    def _proxy_is_expired(self, proxy_name: str) -> bool:
        return time() > self.keep_live_registry[proxy_name]

    def get_proxy_access(self, unique_name: str) -> GlueAccess:
        proxy_data = self.proxy_registry.get(unique_name, None)
        if proxy_data is None:
            raise GlueProxyNotFoundError(unique_name)

        # Handle both old format (just access string) 
        # and new format (dict with access and signature)
        if isinstance(proxy_data, dict):
            return proxy_data['access']
        return proxy_data

    def get_proxy_signature(self, unique_name: str) -> str | None:
        """Get the registered signature for a proxy's context_data."""
        proxy_data = self.proxy_registry.get(unique_name, None)
        if proxy_data is None:
            raise GlueProxyNotFoundError(unique_name)

        if isinstance(proxy_data, dict):
            return proxy_data.get('signature')
        return None

    @staticmethod
    def _compute_context_signature(context_data: dict) -> str:
        """
        Compute a cryptographic signature for context_data.

        Uses HMAC-SHA256 with Django's SECRET_KEY to ensure the signature
        cannot be forged without knowing the secret.
        """
        # Serialize to JSON with sorted keys for consistent hashing
        data_str = json.dumps(context_data, sort_keys=True, default=str)
        secret = django_settings.SECRET_KEY.encode('utf-8')
        return hmac.new(secret, data_str.encode('utf-8'), hashlib.sha256).hexdigest()

    def verify_action_signature(self, unique_name: str, context_data: dict) -> None:
        """
        Verify that the provided context_data matches the registered signature.

        Raises GlueContextDataTamperingError if the signature doesn't match.
        """
        expected_signature = self.get_proxy_signature(unique_name)
        if expected_signature is None:
            # No signature stored (legacy proxy or signature not required)
            return

        actual_signature = _compute_context_signature(context_data)
        if actual_signature != expected_signature:
            raise GlueContextDataTamperingError(unique_name)

    def register_proxy(self, proxy: BaseGlueProxy) -> None:
        context_data = proxy.to_context_data()
        signature = _compute_context_signature(context_data)

        self.proxy_registry[proxy.unique_name] = {
            'access': proxy.access,
            'signature': signature,
        }

        self.keep_live_registry.setdefault(proxy.unique_name, self._get_next_expire_time())

        self._set_modified()

        if not hasattr(self.request, '__glue_context_data__'):
            self.request.__glue_context_data__ = {}

        self.request.__glue_context_data__[proxy.unique_name] = context_data

    def purge_expired_proxies(self) -> None:
        proxy_names_to_purge = [
            proxy_name
            for proxy_name in self.keep_live_registry
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
