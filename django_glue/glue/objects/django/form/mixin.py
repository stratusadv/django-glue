from __future__ import annotations

import inspect
from typing import Any, Mapping, MutableMapping, cast

from django import forms
from django.db.models import Model
from django.forms.models import ModelForm
from pydantic import BaseModel

from django_glue.utils import get_attr_from_path_string


class ModelGlueFormConfigMixin:
    @staticmethod
    def _ensure_form_instance(
        form_or_class: forms.ModelForm | type[forms.ModelForm],
    ) -> forms.ModelForm:
        """Convert a form class to an instance if needed."""
        if inspect.isclass(form_or_class):
            return form_or_class()
        return form_or_class

    @staticmethod
    def normalize_forms(
        form: forms.ModelForm | type[forms.ModelForm] | None,
        forms: Mapping[str, forms.ModelForm | type[forms.ModelForm]] | None,
    ) -> dict[str, forms.ModelForm]:
        normalized = {
            name: ModelGlueFormConfigMixin._ensure_form_instance(f)
            for name, f in (forms or {}).items()
        }

        if form is not None and 'default' in normalized:
            msg = "Use either form or forms['default'], not both."
            raise ValueError(msg)

        if form is not None:
            normalized['default'] = ModelGlueFormConfigMixin._ensure_form_instance(form)

        return normalized

    def serialize_forms(
        self,
        forms: Mapping[str, forms.ModelForm],
    ) -> dict[str, dict]:
        return {
            name: {
                'form_class_path': f'{form.__class__.__module__}.{form.__class__.__name__}',
                'initial': form.initial,
                'target_pk': getattr(getattr(self, 'instance', None), 'pk', None)
            }
            for name, form in forms.items()
        }

    @classmethod
    def deserialize_form_classes(
        cls,
        form_identities: Mapping[str, dict],
        instance: Model | None = None
    ) -> dict[str, ModelForm]:
        forms = {}

        for name, form_identity in form_identities.items():
            model_form_class = cast(
                'type',
                get_attr_from_path_string(form_identity['form_class_path'])
            )

            if not issubclass(model_form_class, ModelForm):
                msg = (
                    f'Invalid form instance of class {model_form_class.__name__} passed '
                    f'to Glue of type {cls}. All forms passed to Model '
                    f'or QuerySet Glue must be ModelForms.'
                )

                raise TypeError(msg)

            forms[name] = model_form_class(
                initial=form_identity['initial'],
                instance=instance
            )

        return forms
