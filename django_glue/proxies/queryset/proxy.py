from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from django.db.models import QuerySet, Model
from django.utils.functional import cached_property

from django_glue.access.access import GlueAccess
from django_glue.exceptions import GlueQuerySetFilterValidationError, GlueModelInstanceNotFoundError
from django_glue.proxies import GlueModelInstanceProxy
from django_glue.bound_attributes.decorators import Attribute
from django_glue.proxies.model.proxy import BaseGlueModelProxy
from django_glue.proxies.policy import ProxyPolicy
from django_glue.proxies.queryset.state import GlueQuerySetProxyState

if TYPE_CHECKING:
    from django.http import HttpRequest
    from django.forms.models import ModelForm
    from django_glue.proxies.policy import ProxyPolicy


_slice = slice


class GlueQuerySetProxy(BaseGlueModelProxy):
    """Proxy for a Django queryset collection."""

    _subject_type = QuerySet
    _state_class = GlueQuerySetProxyState

    @classmethod
    def register( # pyright: ignore[reportIncompatibleMethodOverride]
        cls,
        request: HttpRequest,
        target: QuerySet,
        name: str,
        access: GlueAccess = GlueAccess.VIEW,
        namespace: str = 'querySet',
        fields: Sequence | dict = (),
        exclude: Sequence[str] = (),
        form_class: type[ModelForm] | None = None,
    ) -> None:
        model_class = target.model
        model_instance = model_class()
        state, form_class_path = cls._build_state(model_instance, fields, exclude, form_class)
        state.queryset = target
        proxy = cls(name=name, namespace=namespace, access=access, state=state)
        proxy._form_class_path = form_class_path
        proxy._register_with_request(request)

    @property
    def _custom_policy_details(self) -> dict:
        from django_glue.utils import serialize_queryset  # noqa: PLC0415

        return {
            'encoded_queryset': serialize_queryset(self.state.queryset),
        } | super()._custom_policy_details

    @cached_property
    def _select_related_field_names(self) -> set[str]:
        select_related_dict = self.state.queryset.query.select_related
        if select_related_dict:
            return {
                name for name in self._field_metadata
                if name in select_related_dict
            }
        return set()

    @cached_property
    def _m2m_field_names(self) -> set[str]:
        model_class = self.state.model.__class__
        return {
            f.name for f in model_class._meta.many_to_many
            if f.name in self._field_metadata
        }

    @cached_property
    def _non_m2m_field_names(self) -> set[str]:
        return {
            name for name in self._field_metadata
            if name not in self._m2m_field_names
        }

    @cached_property
    def _field_args_for_values_query(self) -> set[str]:
        model_class = self.state.model.__class__
        fields = [model_class._meta.pk.name]
        for field_name in self._non_m2m_field_names:
            if field_name in self._select_related_field_names:
                field_obj = model_class._meta.get_field(field_name)
                related_model = field_obj.related_model
                for related_model_field in related_model._meta.fields:
                    fields.append(f'{field_name}__{related_model_field.name}')
            else:
                fields.append(field_name)

        return {*fields, *self.state.queryset.query.annotations}

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
        model_class = self.state.model.__class__

        if self._m2m_field_names:
            pk_field = model_class._meta.pk.name
            instances = self.state.queryset.prefetch_related(*self._m2m_field_names)
            instance_map = {getattr(inst, pk_field): inst for inst in instances}

            for item in output_data:
                instance = instance_map[item[pk_field]]
                for m2m_name in self._m2m_field_names:
                    item[m2m_name] = [
                        {'pk': related.pk, '__str__': str(related)}
                        for related in getattr(instance, m2m_name).all()
                    ]

    def _build_child_model_policy(self, item: dict) -> ProxyPolicy:
        from django_glue.proxies.policy import ProxyPolicy  # noqa: PLC0415

        pk_field = self.state.model.__class__._meta.pk.name
        child_name = f'{self.name}__{item[pk_field]}'

        child_subject_details = {
            'namespace': 'model',
            'model_class_path': self._custom_policy_details['model_class_path'],
            'pk_field_name': self._custom_policy_details['pk_field_name'],
            'included_fields': self._custom_policy_details['included_fields'],
            'target_pk': item[pk_field],
        }
        if 'form_class_path' in self._custom_policy_details:
            child_subject_details['form_class_path'] = self._custom_policy_details['form_class_path']

        return ProxyPolicy.new_signed_policy({
            'session_id': self.session_id,
            'name': child_name,
            'access': self.access,
            'bound_attributes': self._child_model_bound_attributes,
            'subject_details': child_subject_details,
        })

    @cached_property
    def _child_model_bound_attributes(self) -> dict[str, Any]:
        child_proxy = self._create_model_proxy_from_instance()
        return {
            name: binding.model_dump(exclude_none=True)
            for name, binding in child_proxy.discover_bound_attributes().items()
        }

    @property
    def _output_data(self) -> list[dict]:
        output_data = list(
            self.state.queryset.values(*self._field_args_for_values_query)
        )

        for obj_dict in output_data:
            self._roll_up_related_fields_in_obj_dict(obj_dict)

        self._add_m2m_field_to_output_data(output_data)

        for item in output_data:
            child_policy = self._build_child_model_policy(item)
            item['__policy__'] = child_policy.model_dump(exclude_none=True)

        return output_data

    def _validate_filter_keys(self, payload: dict) -> None:
        for key in payload:
            base_field = key.split('__')[0]
            if base_field not in self._field_metadata:
                raise GlueQuerySetFilterValidationError(
                    field=base_field,
                    allowed_fields=list(self._field_metadata.keys()),
                )

    @Attribute(access=GlueAccess.VIEW)
    def query_with_params(
        self,
        request: HttpRequest,
        filter: dict | None = None,
        order_by: list | str | None = None,
        slice: dict | None = None,
    ) -> None:
        if filter:
            self._validate_filter_keys(filter)
            self.state.queryset = self.state.queryset.filter(**filter)

        if order_by:
            if isinstance(order_by, str):
                order_by = [order_by]
            self.state.queryset = self.state.queryset.order_by(*order_by)

        if slice:
            self.state.queryset = self.state.queryset[
                _slice(
                    slice.get('start'),
                    slice.get('stop'),
                )
            ]

        self.state.list_data = self._output_data

    @property
    def targets(self) -> list[Any]:
        return [self.state.queryset, *super().targets]

    def _get_model_instance_by_pk(self, pk: int | str) -> Model:
        try:
            return self.state.queryset.get(pk=pk)
        except self.state.queryset.model.DoesNotExist:
            raise GlueModelInstanceNotFoundError(  # noqa: B904
                model_name=self.state.queryset.model.__name__,
                pk=pk,
            )

    def _create_model_proxy_from_instance(self) -> GlueModelInstanceProxy:
        from django_glue.proxies.model.instance.state import GlueModelInstanceProxyState  # noqa: PLC0415

        model_state = GlueModelInstanceProxyState(
            model=self.state.model,
            form=self.state.form,
        )
        return GlueModelInstanceProxy(
            name=self.name,
            access=self.access,
            state=model_state,
            namespace='model',
        )

    @Attribute(access=GlueAccess.VIEW)
    def get(self, request: HttpRequest) -> dict:
        return self._create_model_proxy_from_instance().get(request)

    @Attribute(access=GlueAccess.VIEW)
    def new(self, request: HttpRequest) -> dict:
        """Return default values for a new model instance."""
        model_class = self.state.model.__class__
        instance = model_class()
        pk_field_name = model_class._meta.pk.name

        related_field_names = {
            f.name for f in model_class._meta.get_fields()
            if f.is_relation
        }

        defaults = {pk_field_name: None}
        for field_name in self._field_metadata:
            if field_name == pk_field_name:
                continue
            if field_name in related_field_names:
                defaults[field_name] = []
            elif hasattr(instance, field_name):
                defaults[field_name] = getattr(instance, field_name)

        defaults['__policy__'] = self._build_child_model_policy(defaults).model_dump(exclude_none=False)
        return defaults
