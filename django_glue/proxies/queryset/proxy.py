from __future__ import annotations

from django.db.models import QuerySet, Model

from django_glue.access.access import GlueAccess
from django_glue.resolver.action.schemas import ActionPayloadSchema
from django_glue.exceptions import GlueQuerySetFilterValidationError, GlueModelInstanceNotFoundError
from django_glue.proxies import GlueModelProxy
from django_glue.proxies.decorators import action
from django_glue.proxies.model.base import GlueModelProxyBase
from django_glue.utils import serialize_queryset, deserialize_queryset


class GlueQuerySetProxy(GlueModelProxyBase):
    _subject_type = QuerySet

    def __init__(self, target: QuerySet, **kwargs) -> None:
        super().__init__(target=target, **kwargs)

        self.encoded_query = serialize_queryset(target)

    @classmethod
    def from_action_request_data(cls, encoded_query: str, **kwargs) -> GlueQuerySetProxy:
        decoded_queryset = deserialize_queryset(encoded_query)

        return super().from_action_request_data(target=decoded_queryset, **kwargs)

    def get_model_class(self) -> type[Model]:
        return self.target.model

    def _get_model_instance(self) -> Model:
        """
        QuerySet proxy doesn't have a single instance.
        This returns a new unsaved instance for form field extraction only.
        """
        return self.get_model_class()()

    def _build_context_data(self) -> dict:
        return {'encoded_query': self.encoded_query} | super()._build_context_data()

    def _queryset_to_list(self, queryset: QuerySet) -> list:
        model = self.get_model_class()
        m2m_fields = {
            f.name for f in model._meta.many_to_many if f.name in self._form_field_definitions
        }

        non_m2m_fields = [name for name in self._form_field_definitions if name not in m2m_fields]

        # Detect FK fields set via select_related on the queryset
        select_related_dict = getattr(queryset.query, 'select_related', False) or {}
        select_related_field_names = set(select_related_dict.keys())

        # Build values keys: expand FK fields with __ lookups
        related_model_fields = []
        for field_name in non_m2m_fields:
            if field_name in select_related_field_names:
                field_obj = model._meta.get_field(field_name)
                related_model = field_obj.related_model
                for related_model_field in related_model._meta.fields:
                    related_model_fields.append(f'{field_name}__{related_model_field.name}')
            else:
                related_model_fields.append(field_name)

        # Query with expanded keys
        results = list(
            queryset.values(*[*non_m2m_fields, *related_model_fields, *queryset.query.annotations])
        )

        # Reshape flat __ keys back into nested dicts
        for item in results:
            for related_field_name in select_related_field_names:
                if related_field_name not in self._form_field_definitions:
                    continue
                nested = {}
                for field_name, value in list(item.items()):
                    if field_name.startswith(f'{related_field_name}__'):
                        related_model_field_name = field_name.split('__')[1]

                        nested[related_model_field_name] = value
                        del item[field_name]
                item[related_field_name] = nested

        # Fetch M2M values with prefetch to avoid N+1 queries
        if m2m_fields:
            pk_field = model._meta.pk.name

            # Prefetch all instances with their M2M relations in one query per M2M field
            instances = queryset.prefetch_related(*m2m_fields)
            instance_map = {getattr(inst, pk_field): inst for inst in instances}

            for item in results:
                instance = instance_map[item[pk_field]]
                for m2m_name in m2m_fields:
                    item[m2m_name] = list(getattr(instance, m2m_name).values_list('pk', flat=True))

        return results

    def _validate_filter_keys(self, payload: dict) -> None:
        """
        Validates that all filter keys reference only allowed fields.

        Raises GlueQuerySetFilterValidationError if any filter key references a field not in _form_field_definitions.
        """
        for key in payload:
            # Extract base field name from ORM lookup syntax (e.g., 'title__icontains' -> 'title')
            base_field = key.split('__')[0]

            if base_field not in self._form_field_definitions:
                raise GlueQuerySetFilterValidationError(
                    field=base_field, allowed_fields=list(self._form_field_definitions.keys())
                )

    def _apply_query_params(self, params: dict) -> None:
        if order_by := params.get('order_by'):
            if isinstance(order_by, str):
                order_by = [order_by]
            self.target = self.target.order_by(*order_by)

        if filter_params := params.get('filter'):
            self.target = self.target.filter(**filter_params)

        if slice_params := params.get('slice'):
            self.target = self.target[slice(slice_params.get('start'), slice_params.get('stop'))]

    @action(access=GlueAccess.VIEW)
    def query_with_params(self, action_data: ActionPayloadSchema) -> list:
        if action_data.post_data:
            if filter_params := action_data.post_data.get('filter'):
                self._validate_filter_keys(filter_params)
            self._apply_query_params(action_data.post_data)

        return self._queryset_to_list(self.target)

    def _get_model_instance_by_pk(self, pk: int | str) -> Model:
        """
        Retrieves a model instance by primary key from the queryset.

        Raises GlueModelInstanceNotFoundError if the instance does not exist.
        """
        try:
            return self.target.get(pk=pk)
        except self.target.model.DoesNotExist:
            raise GlueModelInstanceNotFoundError(model_name=self.target.model.__name__, pk=pk)

    def _create_model_proxy_from_instance(self, instance: Model) -> GlueModelProxy:
        return GlueModelProxy(
            target=instance,
            unique_name=self.unique_name,
            access=self.access,
            fields=self.fields,
            exclude=self.exclude,
            form_class=self.form_class,
        )

    def _get_target_model_instance_proxy(self, pk: int) -> GlueModelProxy:
        target_instance = self._get_model_instance_by_pk(pk)
        return self._create_model_proxy_from_instance(target_instance)

    @action(access=GlueAccess.CHANGE)
    def save(self, action_data: ActionPayloadSchema) -> dict:
        pk = action_data.post_data.get('id')
        if pk:
            # Update existing instance
            proxy = self._get_target_model_instance_proxy(pk)
        else:
            # Create new instance
            instance = self.get_model_class()()
            proxy = self._create_model_proxy_from_instance(instance)
        return proxy.save(action_data)

    @action(access=GlueAccess.DELETE)
    def delete(self, action_data: ActionPayloadSchema) -> dict:
        pk = action_data.post_data.get('id')
        if pk is None:
            return {'success': False, 'error': 'id is required for delete action'}
        return self._get_target_model_instance_proxy(pk).delete(action_data)

    @action(access=GlueAccess.VIEW)
    def get(self, action_data: ActionPayloadSchema) -> dict:
        pk = action_data.post_data.get('id')
        if pk is None:
            return {'success': False, 'error': 'id is required for get action'}
        return self._get_target_model_instance_proxy(pk).get(action_data)

    @action(access=GlueAccess.VIEW)
    def new(self, action_data: ActionPayloadSchema) -> dict:
        """Return default values for a new model instance."""
        model_class = self.get_model_class()
        instance = model_class()

        # Get FK and M2M field names to skip (can't access M2M on unsaved instance)
        related_field_names = {
            f.name for f in model_class._meta.get_fields()
            if f.is_relation
        }

        defaults = {'id': None}
        for field_name, field_definition in self._form_field_definitions.items():
            if field_name == 'id':
                continue
            if field_name in related_field_names:
                # Related fields default to empty lists
                defaults[field_name] = []
            elif hasattr(instance, field_name):
                defaults[field_name] = getattr(instance, field_name)

        return defaults
