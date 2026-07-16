from typing import Any

from pydantic import BaseModel, RootModel

from django_glue.glue.metadata import GlueMetadata
from django_glue.glue.policy import GluePolicy


class GlueManifest(BaseModel):
    policy: GluePolicy
    metadata: GlueMetadata
    state: dict[str, Any]


class GlueManifestList(RootModel[list[GlueManifest]]):
    pass
