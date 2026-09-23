from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any, cast

from django_glue.exceptions import GlueModelInstanceNotFoundError
from django_glue.glue.queryset_unpickler import model_class_path
from django_glue.utils import get_attr_from_path_string

if TYPE_CHECKING:
    from django.db import models


def _relation_field(model: type[models.Model], relation_name: str) -> Any:
    for relation in model._meta.related_objects:
        if relation.get_accessor_name() == relation_name:
            return relation
    return model._meta.get_field(relation_name)


@dataclass(frozen=True, slots=True, kw_only=True)
class OwningRelation:
    """The signed to-many relation a queryset's rows are drawn from.

    A draft created through ``relation.new()`` attaches to exactly this
    relation on its first save (state-model.md §4 "Relation membership"). One
    exists only when generic creation can attach: the owner is saved, and the
    relation is a reverse foreign key or a many-to-many whose through model
    Django created (a custom through model needing more values requires an
    explicit callable).
    """

    owner_model_class_path: str
    owner_pk: Any
    relation_name: str

    @classmethod
    def creatable(cls, owner: models.Model, relation_name: str) -> OwningRelation | None:
        if owner.pk is None:
            return None
        field = _relation_field(type(owner), relation_name)
        if field.many_to_many:
            through = getattr(field, 'through', None) or field.remote_field.through
            if not through._meta.auto_created:
                return None
        elif not field.one_to_many:
            return None
        return cls(
            owner_model_class_path=model_class_path(type(owner)),
            owner_pk=owner.pk,
            relation_name=relation_name,
        )

    def serialize(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> OwningRelation:
        return cls(**data)

    def owner(self) -> models.Model:
        model = cast('type[models.Model]', get_attr_from_path_string(self.owner_model_class_path))
        try:
            return model._default_manager.get(pk=self.owner_pk)
        except model.DoesNotExist as error:
            raise GlueModelInstanceNotFoundError(
                model_name=model._meta.label,
                pk=self.owner_pk,
            ) from error

    def assign_owner(self, owner: models.Model, instance: models.Model) -> None:
        """Inject the owner into a reverse-foreign-key member before it is
        validated, overriding any client-supplied value."""
        field = _relation_field(type(owner), self.relation_name)
        if field.one_to_many:
            setattr(instance, field.field.name, owner)

    def attach(self, owner: models.Model, instance: models.Model) -> None:
        """Add a saved member to a many-to-many relation."""
        if _relation_field(type(owner), self.relation_name).many_to_many:
            getattr(owner, self.relation_name).add(instance)
