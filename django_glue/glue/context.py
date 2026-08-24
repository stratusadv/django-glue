from __future__ import annotations

from typing import Any, Literal, TYPE_CHECKING

from pydantic import BaseModel, ConfigDict
from django_glue.conf import settings

from django_glue import constants
from django_glue.assets import asset_version
from django_glue.constants import DJANGO_GLUE_MANIFEST_REQUEST_ATTR_KEY
from django_glue.glue.loading import LoadingStrategy

if TYPE_CHECKING:
    from django_glue.glue.base import BaseGlue
    from django.http import HttpRequest


class GlueManifest(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    is_glue_manifest: Literal[True] = True
    policy_token: str
    metadata: dict[str, Any]
    state: dict[str, Any] = {}
    loading_strategy: LoadingStrategy = LoadingStrategy.LAZY


class GlueContextManager:
    def __init__(self, request: HttpRequest) -> None:
        self.request = request

        # Glue View requests are wrappers; their Glue objects belong to the
        # underlying request so the outer GlueViewFragmentResolver can serialize them.
        context_request = getattr(request, 'glue_context_request', request)
        self.glue_objects: list[BaseGlue] = context_request.__dict__.setdefault(
            DJANGO_GLUE_MANIFEST_REQUEST_ATTR_KEY,
            [],
        )

    @property
    def manifests(self) -> list[BaseGlue]:
        return self.glue_objects

    @property
    def serialized_manifests(self) -> list[dict[str, Any]]:
        return [glue.manifest.model_dump() for glue in self.glue_objects]

    def add_glue(self, glue: BaseGlue) -> BaseGlue:
        # Ensure session exists (Django creates sessions lazily)
        if not self.request.session.session_key:
            self.request.session.create()

        glue.request = self.request
        self.glue_objects.append(glue)
        return glue

    @property
    def _glue_client_context(self) -> dict[str, Any]:
        return {
            'manifest_list': self.serialized_manifests,
            'urls': {
                constants.CALLABLE_ATTRIBUTE_URL_NAME: (
                    f'/{constants.BASE_URL_NAME}/{constants.CALLABLE_ATTRIBUTE_URL_NAME}/'
                ),
                constants.GLUE_VIEW_URL_NAME: (
                    f'/{constants.BASE_URL_NAME}/{constants.GLUE_VIEW_URL_NAME}/'
                ),
            },
            'config': {
                'requestTimeoutSeconds': settings.DJANGO_GLUE_REQUEST_TIMEOUT_SECONDS,
                'csrfCookieName': settings.CSRF_COOKIE_NAME,
            },
        }

    @property
    def context_data(self) -> dict[str, Any]:
        return {
            constants.DJANGO_GLUE_CONTEXT_KEY: self._glue_client_context,
            constants.DJANGO_GLUE_VERSION_KEY: constants.__VERSION__,
            constants.DJANGO_GLUE_ASSET_VERSION_KEY: asset_version(),
            constants.DJANGO_GLUE_CONTEXT_SCRIPT_NAME_KEY: constants.DJANGO_GLUE_CONTEXT_SCRIPT_NAME
        }
