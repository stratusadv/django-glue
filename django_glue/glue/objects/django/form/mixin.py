from __future__ import annotations

from typing import Mapping

from django import forms

from django_glue.utils import get_attr_from_path_string


class FormClassConfigMixin:
    @staticmethod
    def normalize_form_classes(
        form_class: type[forms.ModelForm] | None,
        form_classes: Mapping[str, type[forms.ModelForm]] | None,
    ) -> dict[str, type[forms.ModelForm]]:
        normalized = dict(form_classes or {})

        if form_class is not None and 'default' in normalized:
            raise ValueError("Use either form_class or form_classes['default'], not both.")

        if form_class is not None:
            normalized['default'] = form_class

        return normalized

    @staticmethod
    def serialize_form_class_paths(
        form_classes: Mapping[str, type[forms.ModelForm]],
    ) -> dict[str, str]:
        return {
            name: f'{form_class.__module__}.{form_class.__name__}'
            for name, form_class in form_classes.items()
        }

    @staticmethod
    def deserialize_form_classes(
        form_class_paths: Mapping[str, str],
    ) -> dict[str, type[forms.ModelForm]]:
        return {
            name: get_attr_from_path_string(form_class_path)
            for name, form_class_path in form_class_paths.items()
        }
