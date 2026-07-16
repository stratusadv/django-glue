from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from django_glue import constants
from django_glue.conf import settings
from django_glue.glue.manifest import GlueManifest


class GlueContext(BaseModel):
    urls: dict[str, Any]
    config: dict[str, Any] # TODO: make class for this
    manifest_list: list[GlueManifest]

    @classmethod
    def from_manifest_list(cls, manifest_list: list[GlueManifest] | None = None) -> GlueContext:
        return GlueContext(
            manifest_list=list(manifest_list or []),
            urls={
                constants.CALLABLE_ATTRIBUTE_URL_NAME: (
                    f'/{constants.BASE_URL_NAME}/{constants.CALLABLE_ATTRIBUTE_URL_NAME}/'
                ),
                constants.GLUE_VIEW_URL_NAME: f'/{constants.BASE_URL_NAME}/{constants.GLUE_VIEW_URL_NAME}/',
            },
            config={
                'requestTimeoutSeconds': settings.DJANGO_GLUE_REQUEST_TIMEOUT_SECONDS,
            },
        )

