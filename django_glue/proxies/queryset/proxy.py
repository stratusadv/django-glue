from __future__ import annotations

from typing import Any, TYPE_CHECKING

from django.db.models import QuerySet, Model
from django.utils.functional import cached_property

from django_glue.access.access import GlueAccess
from django_glue.exceptions import GlueQuerySetFilterValidationError, GlueModelInstanceNotFoundError
from django_glue.proxies import GlueModelProxy
from django_glue.proxies.decorators import action
from django_glue.proxies.model.base import GlueModelProxyBase
from django_glue.utils import serialize_queryset, deserialize_queryset

if TYPE_CHECKING:
    from django_glue.resolver.action.schemas import ActionPayloadSchema


class GlueQuerySetProxy(GlueModelProxyBase):
    _subject_type = QuerySet

    def __init__(self, target: QuerySet, **kwargs) -> None:
        super().__init__(target=target, **kwargs)

        self.encoded_query = serialize_queryset(target)

    @classmethod
    def from_action_request_data(cls, encoded_query: str, **kwargs) -> GlueQuerySetProxy:
        decoded_queryset = deserialize_queryset(encoded_query)

        return super().from_action_request_data(target=decoded_queryset, **kwargs)

    def _register_subject_actions(self):
        # TODO: this can be inherited from modelbase
        queryset_class = self.get_model_class().objects.get_queryset().__class__
        self._register_actions(subject_type=queryset_class, category='queryset')
        self._register_actions(subject_type=self.get_model_class(), category='model')

        if self.form_class is not None:
            self._register_actions(subject_type=self._get_form_class(), category='form')

    def _get_subject_action_target_by_category(
        self,
        category: str,
        action_payload: ActionPayloadSchema
    ) -> Any:
        instance_id = action_payload.context_data.get('instance_id')
        match category:
            case 'model':
                return self._get_model_instance_by_pk(pk=instance_id)
            case 'form':
                model = self._get_model_instance_by_pk(pk=instance_id)
                # TODO: pass model to form
                return self._get_form_instance()
            case 'queryset':
                return self.target
            case _:
                return None

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

    @cached_property
    def _select_related_field_names(self) -> set[str]:
        select_related_dict = getattr(self.target.query, 'select_related')

        if select_related_dict:
            return set(
                name for name in self._form_field_definitions
                if name in select_related_dict
            )

        return set()

    @cached_property
    def _m2m_field_names(self) -> set[str]:
        model_class = self.get_model_class()
        return {
            f.name for f in model_class._meta.many_to_many if
            f.name in self._form_field_definitions
        }

    @cached_property
    def _non_m2m_field_names(self) -> set[str]:
        return set([
            name for name in self._form_field_definitions if
            name not in self._m2m_field_names
        ])

    @cached_property
    def _field_args_for_values_query(self) -> set[str]:
        model = self.get_model_class()
        fields = []
        for field_name in self._non_m2m_field_names:
            if field_name in self._select_related_field_names:
                # Expand each field in the related model using dunder notation
                field_obj = model._meta.get_field(field_name)
                related_model = field_obj.related_model
                for related_model_field in related_model._meta.fields:
                    fields.append(f'{field_name}__{related_model_field.name}')
            else:
                fields.append(field_name)

        return {*fields, *self.target.query.annotations}

    def _roll_up_related_fields_in_obj_dict(self, obj_dict: dict):
        for related_field_name in self._select_related_field_names:
            nested = {}
            for name, value in list(obj_dict.items()):
                if name.startswith(f'{related_field_name}__'):
                    related_model_field_name = name.split('__')[1]

                    nested[related_model_field_name] = value
                    del obj_dict[name]
            obj_dict[related_field_name] = nested

    def _add_m2m_field_to_output_data(self, output_data: list[dict]):
        if self._m2m_field_names:
            pk_field = self.get_model_class()._meta.pk.name

            # Prefetch all instances with their M2M relations in one query per M2M field
            instances = self.target.prefetch_related(*self._m2m_field_names)
            instance_map = {getattr(inst, pk_field): inst for inst in instances}

            for item in output_data:
                instance = instance_map[item[pk_field]]
                for m2m_name in self._m2m_field_names:
                    item[m2m_name] = list(
                        getattr(instance, m2m_name).values_list('pk', flat=True))

    @property
    def _output_data(self) -> list[dict]:
        output_data = list(
            self.target.values(*self._field_args_for_values_query)
        )

        for obj_dict in output_data:
            self._roll_up_related_fields_in_obj_dict(obj_dict)

        self._add_m2m_field_to_output_data(output_data)

        return output_data

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
            self.target = self.target[
                slice(slice_params.get('start'),
                      slice_params.get('stop'))
            ]

    @action(access=GlueAccess.VIEW)
    def query_with_params(self, request, post_data: dict = None) -> list:
        if post_data:
            if filter_params := post_data.get('filter'):
                self._validate_filter_keys(filter_params)
            self._apply_query_params(post_data)

        return self._output_data

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
    def save(self, request, context_data: dict = None, post_data: dict = None, file_data: dict = None) -> dict:
        context_data = context_data or {}
        instance_id = context_data.get('instance_id')
        if instance_id:
            # Update existing instance
            proxy = self._get_target_model_instance_proxy(instance_id)
        else:
            # Create new instance
            instance = self.get_model_class()()
            proxy = self._create_model_proxy_from_instance(instance)
        return proxy.save(request, post_data=post_data, file_data=file_data)

    @action(access=GlueAccess.DELETE)
    def delete(self, request, context_data: dict = None) -> dict:
        context_data = context_data or {}
        instance_id = context_data.get('instance_id')
        if instance_id is None:
            return {'success': False, 'error': 'instance_id is required for delete action'}
        return self._get_target_model_instance_proxy(instance_id).delete(request)

    @action(access=GlueAccess.VIEW)
    def get(self, request, context_data: dict = None) -> dict:
        context_data = context_data or {}
        instance_id = context_data.get('instance_id')
        if instance_id is None:
            return {'success': False, 'error': 'instance_id is required for get action'}
        return self._get_target_model_instance_proxy(instance_id).get(request)

    @action(access=GlueAccess.VIEW)
    def new(self, request) -> dict:
        """Return default values for a new model instance."""
        model_class = self.get_model_class()
        instance = model_class()

        # Get related field names to skip (can't access related fields on unsaved instance)
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
