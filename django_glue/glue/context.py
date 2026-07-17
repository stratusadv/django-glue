from __future__ import annotations

from typing import Any, TYPE_CHECKING

from pydantic import BaseModel
from django_glue.conf import settings

from django_glue import constants
from django_glue.constants import DJANGO_GLUE_MANIFEST_REQUEST_ATTR_KEY
from django_glue.glue.policy import GluePolicy  # noqa: TC001
from django_glue.glue.metadata import GlueMetadata  # noqa: TC001

if TYPE_CHECKING:
    from django_glue.glue.base import BaseGlue
    from django.http import HttpRequest


class GlueManifest(BaseModel):
    policy: GluePolicy
    metadata: GlueMetadata


class GlueContextManager:
    def __init__(self, request: HttpRequest) -> None:
        self.manifests: list[GlueManifest] = \
            request.__dict__.setdefault(DJANGO_GLUE_MANIFEST_REQUEST_ATTR_KEY, [])

    def add_glue(self, glue: BaseGlue) -> None:
        self.manifests.append(glue.manifest)

    @property
    def _glue_client_context(self) -> dict[str, Any]:
        return {
            'manifest_list': [manifest.model_dump() for manifest in self.manifests],
            'urls': {
                constants.CALLABLE_ATTRIBUTE_URL_NAME: (
                    f'/{constants.BASE_URL_NAME}/{constants.CALLABLE_ATTRIBUTE_URL_NAME}/'
                ),
                constants.GLUE_VIEW_URL_NAME: f'/{constants.BASE_URL_NAME}/{constants.GLUE_VIEW_URL_NAME}/',
            },
            'config': {
                'requestTimeoutSeconds': settings.DJANGO_GLUE_REQUEST_TIMEOUT_SECONDS,
            },
        }

    @property
    def context_data(self) -> dict[str, Any]:
        return {
            constants.DJANGO_GLUE_CONTEXT_KEY: self._glue_client_context,
            constants.DJANGO_GLUE_VERSION_KEY: constants.__VERSION__,
            constants.DJANGO_GLUE_CONTEXT_SCRIPT_NAME_KEY: constants.DJANGO_GLUE_CONTEXT_SCRIPT_NAME
        }
