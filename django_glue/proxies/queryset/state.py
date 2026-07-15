from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django_glue.proxies.form.state import GlueFormProxyState

if TYPE_CHECKING:
    from django.db.models import Model, QuerySet
    from django.forms.models import ModelForm
    from django_glue.resolver.attribute_event.schemas import BoundProxyAttributeEvent


class GlueQuerySetProxyState(GlueFormProxyState):
    """State for a queryset proxy — holds the Django queryset, model, and form instances."""

    namespace = 'querySet'

    def __init__(
        self,
        queryset: QuerySet,
        model: Model,
        form: ModelForm,
        instance_pk: int | str | None = None,
    ) -> None:
        super().__init__(form)
        self.queryset = queryset
        self.model = model
        self.instance_pk = instance_pk
        self.list_data: list[dict[str, Any]] | None = None

    def serialize(self, field_names: list[str] | None = None) -> dict:
        from django_glue.proxies.model.proxy import BaseGlueModelProxy  # noqa: PLC0415

        return {
            'namespace': self.namespace,
            'instance_data': BaseGlueModelProxy._serialize_model_instance(
                self.model,
                field_names or list(self.form.fields),
            ),
            'errors': dict(self.form.errors),
            'instance_pk': self.instance_pk,
            'list_data': self.list_data,
        }

    @classmethod
    def deserialize(cls, event: BoundProxyAttributeEvent) -> GlueQuerySetProxyState:
        from django.forms import modelform_factory  # noqa: PLC0415
        from django_glue.utils import get_attr_from_path_string  # noqa: PLC0415
        from django_glue.utils import deserialize_queryset  # noqa: PLC0415

        subject_details = event.policy.subject_details
        model_class = get_attr_from_path_string(subject_details.model_class_path)

        if subject_details.form_class_path:
            form_class = get_attr_from_path_string(subject_details.form_class_path)
        else:
            from django_glue.proxies.model.proxy import BaseGlueModelProxy  # noqa: PLC0415

            form_class = modelform_factory(
                model_class,
                fields=BaseGlueModelProxy._editable_model_field_names(
                    model_class,
                    list(subject_details.included_fields.keys()),
                ),
            )

        state_data = event.proxy_state
        instance_pk = state_data.get('instance_pk') if state_data else None
        model = model_class.objects.filter(pk=instance_pk).first() or model_class()

        if state_data and state_data.get('instance_data'):
            if event.request.FILES:
                form = form_class(
                    data=state_data['instance_data'],
                    instance=model,
                    files=event.request.FILES or None,
                )
            else:
                form = form_class(
                    initial=state_data['instance_data'],
                    instance=model,
                    files=event.request.FILES or None,
                )
        else:
            form = form_class(instance=model, files=event.request.FILES or None)

        queryset = deserialize_queryset(subject_details.encoded_queryset)

        return cls(queryset=queryset, model=model, form=form, instance_pk=instance_pk)
