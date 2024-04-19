from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from typing import Union

from django.contrib.contenttypes.models import ContentType

from django_glue.access.enums import GlueAccess
from django_glue.handler.enums import GlueConnection


@dataclass
class GlueSessionData(ABC):
    connection: GlueConnection
    access: GlueAccess

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class GlueMetaData(ABC):
    """
        # Todo: Should this handle both queryset and models? Should this be split into two classes?
        This class is used to store meta data about the model or query set.
    """
    # app_label: str = None
    # model: str = None
    # object_pk: int = None
    query_set_str: str = None
    template: str = None
    function: str = None
    # fields: Union[list, tuple] = None
    # exclude: Union[list, tuple] = None
    # methods: Union[list, tuple] = None

    @property
    def model_class(self):
        return ContentType.objects.get_by_natural_key(self.app_label, self.model).model_class()

    def to_dict(self) -> dict:
        return asdict(self)
