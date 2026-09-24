from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel
from django_glue.conf import settings

from django_glue import constants
from django_glue.assets import asset_version
from django_glue.constants import DJANGO_GLUE_MANIFEST_REQUEST_ATTR_KEY

if TYPE_CHECKING:
    from django_glue.glue.base import BaseGlue
    from django.http import HttpRequest

TGlue = TypeVar('TGlue', bound='BaseGlue')


class GlueObjectEntry(BaseModel):
    """
    Addressed wire entry (state-model.md §10): the page-load and
    attribute-call entry shape, without a result tag.
    """

    address: str = ''
    policy_token: str
    static_data: dict[str, Any] = {}
    computed_data: dict[str, Any] = {}


class GlueContextManager:
    def __init__(self, request: HttpRequest) -> None:
        self.request = request
        self.glue_objects: list[BaseGlue] = request.__dict__.setdefault(
            DJANGO_GLUE_MANIFEST_REQUEST_ATTR_KEY,
            [],
        )

    @property
    def serialized_objects(self) -> list[dict[str, Any]]:
        """
        The page's object graph as flat addressed entries (state-model.md
        §10 "Page load"): roots first, children as flat siblings, deduped by
        address.
        """
        serialized: list[dict[str, Any]] = []
        seen: set[str] = set()
        for glue in self.glue_objects:
            if glue.address in seen:
                continue

            seen.add(glue.address)
            serialized.append(glue.entry.model_dump())

            for child_entry in glue._serialized_child_entries():
                if child_entry['address'] in seen:
                    continue

                seen.add(child_entry['address'])
                serialized.append(child_entry)

        return serialized

    def add_glue(self, glue: TGlue) -> TGlue:
        glue.introduce(self.request)

        # Ensure session exists (Django creates sessions lazily)
        if not self.request.session.session_key:
            self.request.session.create()

        self.glue_objects.append(glue)
        return glue

    @property
    def _glue_client_context(self) -> dict[str, Any]:
        return {
            'objects': self.serialized_objects,
            'urls': {
                constants.CALLABLE_ATTRIBUTE_URL_NAME: (
                    f'/{constants.BASE_URL_NAME}/{constants.CALLABLE_ATTRIBUTE_URL_NAME}/'
                ),
            },
            'config': {
                'requestTimeoutSeconds': settings.DJANGO_GLUE_REQUEST_TIMEOUT_SECONDS,
                'csrfCookieName': settings.CSRF_COOKIE_NAME,
                'glueViewMediaType': constants.GLUE_VIEW_MEDIA_TYPE,
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
