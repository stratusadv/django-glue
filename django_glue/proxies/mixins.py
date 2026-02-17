from abc import ABC, abstractmethod
from typing import Any, Sequence

from django.db.models import ForeignObjectRel
from django.utils.functional import cached_property

from django_glue.proxies.proxy import BaseGlueProxy


class GlueProxyFieldsMixin(BaseGlueProxy, ABC):
    def __init__(
        self,
        fields: Sequence = (),
        exclude: Sequence = (),
        **kwargs
    ):
        super().__init__(**kwargs)
        self.fields = fields
        self.exclude = exclude

    @abstractmethod
    def get_model_class(self):
        raise NotImplementedError("Subclasses must implement model_class property")

    def to_session_data(self) -> dict:
        return (
            super().to_session_data() |
            {
                'fields': self.fields,
                'exclude': self.exclude
            } |
            self._build_session_data()
        )

    @cached_property
    def _included_fields(self) -> dict[str, Any]:
        # TODO: we should probably ensure id is in included fields due to how we are
        # queryset instance updates

        deconstructed_fields = [
            field.deconstruct()
            for field in self.get_model_class()._meta.get_fields()
            if (
                    not isinstance(field, ForeignObjectRel) and
                    not field.__class__.__name__ == 'GenericRelation' and
                    not field.name in self.exclude and
                    (not self.fields or field.name in self.fields)
            )
        ]

        return {
            field_name: {
                'type': field_type,
                **{
                    opt_name: opt_value
                    for opt_name, opt_value in field_options.items()
                    if opt_name not in ['default']
                }
            }
            for field_name, field_type, _, field_options in deconstructed_fields
        }
