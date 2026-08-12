from __future__ import annotations

from typing import Any, Sequence, TYPE_CHECKING

from django_glue.glue.attributes.django.model.field import ModelFieldAttribute

if TYPE_CHECKING:
    from django.db import models

    from django_glue.access import GlueAccess
    from django_glue.glue.base import BaseGlue
    from django_glue.glue.objects.django.model.object import ModelGlue


class ForeignKeyFieldAttribute(ModelFieldAttribute):
    """GlueAttribute for a Django ForeignKey or OneToOneField.

    Extends ModelFieldAttribute to support serializing FK relationships
    as nested model proxies for object-graph navigation.

    Frontend usage:
        - model.parent -> full model proxy for object navigation
        - model.parent_id -> raw FK id
        - model.form -> use attached form for editing

    Supports both eager loading (when select_related was used) and
    lazy loading (fetched on frontend access via load_fk_proxy attribute).
    """

    namespace = 'related_field'

    def __init__(
        self,
        *,
        owner: BaseGlue,
        name: str,
        field: models.Field,
        instance: models.Model,
        access: GlueAccess,
        options: dict | None = None,
        is_cached: bool = False,
        related_fields: Sequence[str] | None = None,
        related_exclude: Sequence[str] | None = None,
    ) -> None:
        super().__init__(
            owner=owner,
            name=name,
            field=field,
            instance=instance,
            access=access,
            options=options,
        )
        self.is_cached = is_cached
        self.related_fields = related_fields
        self.related_exclude = related_exclude
        self._related_glue = None

    def add_extra_metadata(self, metadata: dict[str, Any]) -> None:
        super().add_extra_metadata(metadata)

        related_model = self.field.related_model

        # Relation metadata
        metadata['choices'] = []
        metadata['pk_field'] = related_model._meta.pk.name
        metadata['choice_model_path'] = f'{related_model.__module__}.{related_model.__name__}'
        metadata['related_model'] = metadata['choice_model_path']
        metadata['choices_cache_key'] = (
            f'{self.instance.__class__._meta.label_lower}.{self.name}.'
            f'{related_model._meta.label_lower}'
        )

        # FK proxy metadata
        metadata['lazy'] = not self.is_cached
        metadata['fk_attname'] = self.field.attname

        # Always include nested glue's metadata if FK has a value
        related_glue = self._get_related_glue()
        if related_glue is not None:
            metadata['glue_namespace'] = related_glue.namespace
            metadata['metadata'] = related_glue.metadata

    def _get_related_instance(self) -> models.Model | None:
        """Get the related instance, returning None if not loaded or null."""
        try:
            return getattr(self.instance, self.name)
        except self.field.related_model.DoesNotExist:
            return None

    def _get_related_glue(self) -> ModelGlue | None:
        """Get or create the ModelGlue for the related instance."""
        if self._related_glue is not None:
            return self._related_glue

        related_instance = self._get_related_instance()
        if related_instance is None:
            return None

        # Cycle detection: track (model_class, relation_name) pairs to detect
        # when we're about to traverse the same relationship from the same model
        # type again. This allows multiple FKs to the same model (e.g., rival and
        # mentor both pointing to Gorilla) while preventing cycles like:
        # Gorilla.fights → Fight.red_corner → Gorilla.fights (same pair seen)
        visited_relations = getattr(self.owner, '_visited_relations', set())
        owner_model = type(self.instance)
        relation_key = (owner_model, self.name)
        if relation_key in visited_relations:
            return None

        from django_glue.glue.objects.django.model.object import ModelGlue  # noqa: PLC0415

        fields = self.related_fields or '__all__'
        exclude = self.related_exclude or ()

        self._related_glue = ModelGlue(
            related_instance,
            name=f'{self.owner.name}.{self.name}',
            access=self.owner.access,
            fields=fields,
            exclude=exclude,
        )
        self._related_glue.request = self.owner.request

        # Propagate visited relations to prevent cycles in nested objects
        self._related_glue._visited_relations = visited_relations | {relation_key}

        return self._related_glue

    @property
    def glue_object(self) -> ModelGlue | None:
        """Return the nested glue object for policy/metadata generation.

        Always returns a glue object if the FK has a value, enabling both:
        - Eager loading: full state included
        - Lazy loading: policy included, state loaded on frontend access
        """
        return self._get_related_glue()

    @property
    def state(self) -> dict[str, Any] | None:
        """Return nested object state when eager, None when lazy.

        The raw FK value is provided by the separate attname field (e.g., parent_id).
        This mirrors Django where task.parent is the object and task.parent_id is the raw value.
        """
        if self.is_cached:
            related_glue = self._get_related_glue()
            if related_glue is not None:
                return related_glue.state
        return None
