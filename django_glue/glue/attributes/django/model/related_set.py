from __future__ import annotations

from typing import Any, Literal, TYPE_CHECKING

from django_glue.access import GlueAccess
from django_glue.glue.attributes.base import BaseGlueAttribute
from django_glue.glue.loading import LoadingStrategy

if TYPE_CHECKING:
    from django.db import models

    from django_glue.glue.base import BaseGlue
    from django_glue.glue.objects.django.queryset import QuerySetGlue


class RelatedSetFieldAttribute(BaseGlueAttribute):
    """GlueAttribute for reverse FK and M2M relationships as QuerySetGlue.

    Exposes both reverse ForeignKey relations (e.g., author.books where Book
    has FK to Author) and ManyToManyField relations (e.g., gorilla.skills)
    as nested QuerySetGlue objects.

    Supports both eager and lazy loading:
    - Eager: When prefetch_related was used, state includes the items
    - Lazy: When not prefetched, frontend fetches on demand via .all()

    Frontend usage:
        - model.books -> QuerySetGlue proxy for related objects
        - await model.books.all() -> load items (lazy) or return cached (eager)
    """

    namespace = 'related_set'

    def __init__(
        self,
        *,
        owner: BaseGlue,
        name: str,
        instance: models.Model,
        related_model: type[models.Model],
        required_access: GlueAccess,
        is_prefetched: bool = False,
        relation_type: Literal['reverse_fk', 'm2m'],
    ) -> None:
        super().__init__(owner=owner, name=name, required_access=required_access)
        self.instance = instance
        self.related_model = related_model
        self.is_prefetched = is_prefetched
        self.relation_type = relation_type
        self._related_glue: QuerySetGlue | None = None

    @property
    def metadata(self) -> dict[str, Any]:
        base = super().metadata
        base.update({
            'namespace': self.namespace,
            'type': 'ManyToManyField' if self.relation_type == 'm2m' else 'ReverseForeignKey',
            'lazy': not self.is_prefetched,
            'related_model': f'{self.related_model.__module__}.{self.related_model.__name__}',
            'relation_type': self.relation_type,
        })

        # Include nested QuerySetGlue metadata for frontend proxy initialization
        related_glue = self._get_related_glue()
        if related_glue is not None:
            base['glue_namespace'] = related_glue.namespace  # 'querySet'
            base['metadata'] = related_glue.metadata

        return base

    def _get_related_queryset(self) -> models.QuerySet:
        """Get the queryset for the related objects."""
        manager = getattr(self.instance, self.name)
        return manager.all()

    def _get_related_glue(self) -> QuerySetGlue | None:
        """Get or create the QuerySetGlue for the related set."""
        if self._related_glue is not None:
            return self._related_glue

        # Don't create QuerySetGlue if instance is not saved
        if self.instance.pk is None:
            return None

        # Cycle detection: track (model_class, relation_name) pairs to detect
        # when we're about to traverse the same relationship from the same model
        # type again. This allows multiple relations to the same model while
        # preventing cycles like:
        # Gorilla.fights → Fight.red_corner → Gorilla.fights (same pair seen)
        visited_relations = getattr(self.owner, '_visited_relations', set())
        owner_model = type(self.instance)
        relation_key = (owner_model, self.name)
        if relation_key in visited_relations:
            return None

        from django_glue.glue.objects.django.model.object import ALL_FIELDS  # noqa: PLC0415
        from django_glue.glue.objects.django.queryset import QuerySetGlue  # noqa: PLC0415

        queryset = self._get_related_queryset()

        self._related_glue = QuerySetGlue(
            queryset,
            name=f'{self.owner.name}.{self.name}',
            access=GlueAccess.VIEW,  # Read-only for v1
            fields=ALL_FIELDS,
            exclude=(),
            loading_strategy=LoadingStrategy.EAGER if self.is_prefetched else LoadingStrategy.LAZY,
        )
        self._related_glue.request = self.owner.request

        # Propagate visited relations to prevent cycles in nested objects
        self._related_glue._visited_relations = visited_relations | {relation_key}

        return self._related_glue

    @property
    def glue_object(self) -> QuerySetGlue | None:
        """Return the nested QuerySetGlue for policy/metadata generation.

        Always returns a glue object if the instance is saved, enabling both:
        - Eager loading: full state included
        - Lazy loading: policy included, state loaded on frontend access
        """
        return self._get_related_glue()

    @property
    def state(self) -> dict[str, Any] | None:
        """Return nested QuerySetGlue state when prefetched, None when lazy.

        When prefetched (eager), we include the full items list.
        When not prefetched (lazy), frontend must call .all() to load.
        """
        if not self.is_prefetched:
            return None

        related_glue = self._get_related_glue()
        if related_glue is None:
            return None

        # For eager loading, seek-paginate the prefetched instances in memory.
        # This matches QuerySetGlue.query_with_params() output format.
        return related_glue.seek_batch(list(self._get_related_queryset()))

