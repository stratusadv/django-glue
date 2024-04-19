from dataclasses import dataclass, field
from typing import Union

from django_glue.response.data import GlueJsonData
from django_glue.session.data import GlueSessionData


@dataclass
class GlueModelObjectSessionData(GlueSessionData):
    app_label: str = None
    model_name: str = None
    object_pk: int = None
    included_fields: Union[list, tuple] = field(default_factory=tuple)
    exclude_fields: Union[list, tuple] = field(default_factory=tuple)
    methods: Union[list, tuple] = field(default_factory=tuple)


@dataclass
class GlueModelObjectJsonData(GlueJsonData):
    glue_fields: list['GlueModelField'] = field(default_factory=list)

