from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django_glue.glue.base import BaseGlue


class GlueObjectResolverRegistry:
    """Registry for reconstructing GlueObjects from signed policy namespaces."""

    def __init__(self) -> None:
        self.glue_object_classes: dict[str, type[BaseGlue]] = {}

    def register_glue_object_class(self, glue_object_class: type[BaseGlue]) -> None:
        self.glue_object_classes[glue_object_class.namespace] = glue_object_class

    def get_class_for_namespace(self, namespace: str) -> type[BaseGlue]:
        glue_object_class = self.glue_object_classes.get(namespace)
        if glue_object_class is None:
            msg = f"No Glue object registered for namespace '{namespace}'"
            raise KeyError(msg)
        return glue_object_class


glue_object_resolver_registry = GlueObjectResolverRegistry()


def _register_builtins() -> None:
    from django_glue.glue.objects.django.form.object import FormGlue  # noqa: PLC0415
    from django_glue.glue.objects.django.model.object import ModelGlue  # noqa: PLC0415
    from django_glue.glue.objects.django.queryset import QuerySetGlue  # noqa: PLC0415
    from django_glue.glue.objects.django.template import TemplateGlue  # noqa: PLC0415
    from django_glue.glue.function import FunctionGlue  # noqa: PLC0415

    glue_object_resolver_registry.register_glue_object_class(ModelGlue)
    glue_object_resolver_registry.register_glue_object_class(FormGlue)
    glue_object_resolver_registry.register_glue_object_class(QuerySetGlue)
    glue_object_resolver_registry.register_glue_object_class(FunctionGlue)
    glue_object_resolver_registry.register_glue_object_class(TemplateGlue)


_register_builtins()
