from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django_glue.glue.base import BaseGlue


class GlueClassRegistry:
    """Registry for reconstructing instances of Glue classes from signed policy namespaces."""

    def __init__(self) -> None:
        self.glue_object_classes: dict[str, type[BaseGlue]] = {}

    def register_glue_class(self, glue_object_class: type[BaseGlue]) -> None:
        self.glue_object_classes[glue_object_class.namespace] = glue_object_class

    def get_glue_class(self, namespace: str) -> type[BaseGlue]:
        glue_object_class = self.glue_object_classes.get(namespace)
        if glue_object_class is None:
            msg = f"No Glue class registered for namespace '{namespace}'"
            raise KeyError(msg)
        return glue_object_class


glue_class_registry = GlueClassRegistry()


def _register_builtins() -> None:
    from django_glue.glue.collection import CollectionGlue  # noqa: PLC0415
    from django_glue.glue.objects.django.form.object import FormGlue  # noqa: PLC0415
    from django_glue.glue.objects.django.model.object import ModelGlue  # noqa: PLC0415
    from django_glue.glue.objects.django.queryset import QuerySetGlue  # noqa: PLC0415
    from django_glue.glue.objects.django.template import TemplateGlue  # noqa: PLC0415
    from django_glue.glue.function import FunctionGlue  # noqa: PLC0415
    from django_glue.glue.json import JsonGlue  # noqa: PLC0415

    glue_class_registry.register_glue_class(CollectionGlue)
    glue_class_registry.register_glue_class(ModelGlue)
    glue_class_registry.register_glue_class(FormGlue)
    glue_class_registry.register_glue_class(QuerySetGlue)
    glue_class_registry.register_glue_class(FunctionGlue)
    glue_class_registry.register_glue_class(TemplateGlue)
    glue_class_registry.register_glue_class(JsonGlue)


_register_builtins()
