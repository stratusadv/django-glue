from __future__ import annotations

import base64
import pickle
from django.db.models import QuerySet, Model

from django_glue.access.access import GlueAccess
from django_glue.proxies import GlueModelProxy
from django_glue.proxies.mixins import GlueProxyFieldsMixin
from django_glue.proxies.decorators import action


class GlueQuerySetProxy(GlueProxyFieldsMixin):
    _subject_type = QuerySet

    def __init__(
        self,
        target: QuerySet,
        **kwargs
    ):
        super().__init__(target=target, **kwargs)

        self.encoded_query = base64.b64encode(pickle.dumps(target.query)).decode()

    @classmethod
    def from_proxy_registry_data(
        cls,
        encoded_query: str,
        **kwargs
    ) -> GlueQuerySetProxy:
        query = pickle.loads(base64.b64decode(encoded_query))
        decoded_queryset = query.model.objects.all()
        decoded_queryset.query = query

        return cls(
            target=decoded_queryset,
            **kwargs
        )

    def get_model_class(self):
        return self.target.model

    def _build_session_data(self) -> dict:
        return {
            'encoded_query': self.encoded_query,
            **super()._build_session_data()
        }

    def _build_context_data(self) -> dict:
        return {
            'fields': self._included_fields,
        }

    def _queryset_to_list(self, queryset: QuerySet):
        return list(queryset.values(*[
            field_name for field_name
            in self._included_fields.keys()
        ]))

    @action(access=GlueAccess.VIEW)
    def all(self):
        return self._queryset_to_list(self.target)

    @action(access=GlueAccess.VIEW)
    def filter(self, payload: dict):
        return self._queryset_to_list(self.target.filter(**payload))

    def _create_model_proxy_from_instance(self, instance: Model):
        return GlueModelProxy(
            target=instance,
            unique_name=self.unique_name,
            access=self.access,
            fields=self.fields,
            exclude=self.exclude,
        )

    @action(access=GlueAccess.CHANGE)
    def save(self, payload: dict):
        target_instance = self.target.get(pk=payload['id'])
        instance_proxy = self._create_model_proxy_from_instance(target_instance)

        return instance_proxy.save(payload)

    @action(access=GlueAccess.DELETE)
    def delete(self, payload: dict):
        pk = payload['id']

        target_instance = self.target.get(pk=pk)
        instance_proxy = self._create_model_proxy_from_instance(target_instance)

        return instance_proxy.delete()
