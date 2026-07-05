from __future__ import annotations

from typing import TYPE_CHECKING, Self, cast

from django.db.models import QuerySet, Model
from django.http import HttpRequest
from django.utils.functional import cached_property
from django.forms.models import ModelForm

from django_glue.access.access import GlueAccess
from django_glue.exceptions import GlueQuerySetFilterValidationError, GlueModelInstanceNotFoundError
from django_glue.proxies import GlueModelInstanceProxy
from django_glue.proxies.decorators import action
from django_glue.proxies.model.proxy import BaseGlueModelProxy
from django_glue.proxies.queryset.contract import GlueQuerySetProxyContractData
from django_glue.proxies.queryset.state import GlueQuerySetProxyState
from django_glue.utils import deserialize_queryset, get_attr_from_path_string, serialize_queryset

if TYPE_CHECKING:
    from django_glue.resolver.action.schemas import ActionRequest


_slice = slice

class GlueQuerySetProxy(BaseGlueModelProxy):
    _subject_type = QuerySet

    def __init__(
        self,
        queryset: QuerySet,
        instance_pk: int | str | None = None,
        **kwargs
    ) -> None:
        self.queryset = queryset

        model_class = cast('type[Model]' ,queryset.model)
        model_instance = model_class.objects.filter(pk=instance_pk).first() or model_class()

        self._register_actions_for_class(queryset.__class__)

        self.queryset = queryset
        super().__init__(model_instance=model_instance, **kwargs)

    @classmethod
    def _from_action_request(cls, action_request: ActionRequest) -> Self:
        contract_data = GlueQuerySetProxyContractData(**action_request.contract.custom_data)
        state_data = GlueQuerySetProxyState(**action_request.contract.custom_data)

        return cls._from_deconstructed_action_request_data(
            name=action_request.contract.name,
            access=action_request.contract.access,
            model_class_path=contract_data.model_class_path,
            form_class_path=contract_data.form_class_path,
            allowed_fields=contract_data.allowed_fields,
            instance_pk=state_data.instance_pk,
            state=state_data,
            queryset=deserialize_queryset(contract_data.encoded_queryset)
        )

    @property
    def _custom_contract_data(self) -> dict:
        return {
            'encoded_query': serialize_queryset(self.queryset)
        } | super()._custom_contract_data

    @cached_property
    def _select_related_field_names(self) -> set[str]:
        select_related_dict = self.queryset.query.select_related

        if select_related_dict:
            return {
                name for name in self._field_metadata
                if name in select_related_dict
            }

        return set()

    @cached_property
    def _m2m_field_names(self) -> set[str]:
        model_class = self.model_instance.__class__

        return {
            f.name for f in model_class._meta.many_to_many if
            f.name in self._field_metadata
        }

    @cached_property
    def _non_m2m_field_names(self) -> set[str]:
        return {
            name for name in self._field_metadata if
            name not in self._m2m_field_names
        }

    @cached_property
    def _field_args_for_values_query(self) -> set[str]:
        model_class = self.model_instance.__class__
        fields = []
        for field_name in self._non_m2m_field_names:
            if field_name in self._select_related_field_names:
                # Expand each field in the related model using dunder notation
                field_obj = model_class._meta.get_field(field_name)
                related_model = cast('type[Model]', field_obj.related_model)
                for related_model_field in related_model._meta.fields:
                    fields.append(f'{field_name}__{related_model_field.name}')
            else:
                fields.append(field_name)

        return {*fields, *self.queryset.query.annotations}

    def _roll_up_related_fields_in_obj_dict(self, obj_dict: dict) -> None:
        for related_field_name in self._select_related_field_names:
            nested = {}
            for name, value in list(obj_dict.items()):
                if name.startswith(f'{related_field_name}__'):
                    related_model_field_name = name.split('__')[1]

                    nested[related_model_field_name] = value
                    del obj_dict[name]
            obj_dict[related_field_name] = nested

    def _add_m2m_field_to_output_data(self, output_data: list[dict]) -> None:
        model_class = self.model_instance.__class__

        if self._m2m_field_names:
            pk_field = model_class._meta.pk.name

            # Prefetch all instances with their M2M relations in one query per M2M field
            instances = self.queryset.prefetch_related(*self._m2m_field_names)
            instance_map = {getattr(inst, pk_field): inst for inst in instances}

            for item in output_data:
                instance = instance_map[item[pk_field]]
                for m2m_name in self._m2m_field_names:
                    item[m2m_name] = list(
                        getattr(instance, m2m_name).values_list('pk', flat=True))

    @property
    def state(self) -> GlueQuerySetProxyState:
        return GlueQuerySetProxyState(
            instance_data=self.form_instance.data,
            errors=self.form_instance.errors,
            files=self.form_instance.files,
            instance_pk=self.model_instance.pk,
            list_data=self._output_data
        )

    @property
    def _output_data(self) -> list[dict]:
        output_data = list(
            self.queryset.values(*self._field_args_for_values_query)
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

            if base_field not in self._field_metadata:
                raise GlueQuerySetFilterValidationError(
                    field=base_field, allowed_fields=list(self._field_metadata.keys())
                )

    # TODO: need to update the action processor to send in full kwarg dict if the action asks for it
    @action(access=GlueAccess.VIEW)
    def query_with_params(
        self,
        request: HttpRequest,
        filter: dict,
        order_by: list | str,
        slice: dict,
    ) -> None:
        if filter:
            self._validate_filter_keys(filter)
            self.queryset = self.queryset.filter(**filter)

        if order_by:
            if isinstance(order_by, str):
                order_by = [order_by]
            self.queryset = self.queryset.order_by(*order_by)


        if slice:
            self.queryset = self.queryset[
                _slice(
                    slice.get('start'),
                    slice.get('stop')
                )
            ]

    def _get_model_instance_by_pk(self, pk: int | str) -> Model:
        """
        Retrieves a model instance by primary key from the queryset.

        Raises GlueModelInstanceNotFoundError if the instance does not exist.
        """
        try:
            return self.queryset.get(pk=pk)
        except self.queryset.model.DoesNotExist:
            raise GlueModelInstanceNotFoundError(model_name=self.queryset.model.__name__, pk=pk)

    def _create_model_proxy_from_instance(self) -> GlueModelInstanceProxy:
        if self.form_class_path:
            form_class = cast('type[ModelForm]', get_attr_from_path_string(self.form_class_path))
        else:
            form_class = None

        return GlueModelInstanceProxy(
            model_instance=self.model_instance,
            name=self.name,
            access=self.access,
            fields=list(self._field_metadata.keys()),
            form_class=form_class,
        )

    @action(access=GlueAccess.CHANGE)
    def save(self, request: HttpRequest) -> None:
        return self._create_model_proxy_from_instance().save(request)

    @action(access=GlueAccess.DELETE)
    def delete(self, request: HttpRequest) -> None:
        return self._create_model_proxy_from_instance().save(request)

    @action(access=GlueAccess.VIEW)
    def get(self, request: HttpRequest) -> dict:
        return self._create_model_proxy_from_instance().get(request)

    @action(access=GlueAccess.VIEW)
    def new(self, request) -> dict:
        """Return default values for a new model instance."""
        model_class = self.model_instance.__class__
        instance = model_class()
        pk_field_name = model_class._meta.pk.name

        # Get related field names to skip (can't access related fields on unsaved instance)
        related_field_names = {
            f.name for f in model_class._meta.get_fields()
            if f.is_relation
        }

        defaults = {pk_field_name: None}
        for field_name, field_definition in self._field_metadata.items():
            if field_name == pk_field_name:
                continue
            if field_name in related_field_names:
                # Related fields default to empty lists
                defaults[field_name] = []
            elif hasattr(instance, field_name):
                defaults[field_name] = getattr(instance, field_name)

        return defaults
