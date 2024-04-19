from dataclasses import dataclass, field
from typing import Union

from django_glue.session.data import GlueSessionData


@dataclass
class GlueQuerySetSessionData(GlueSessionData):
    unique_name: str
    query_set_str: str
    app_label: str
    model_name: str
    included_fields: Union[list, tuple]
    exclude_fields: Union[list, tuple]
    methods: Union[list, tuple]
