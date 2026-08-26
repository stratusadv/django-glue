from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from typing import Any, Sequence, TYPE_CHECKING

from django_glue.exceptions import GlueQuerySetCursorValidationError

if TYPE_CHECKING:
    from django.db import models


def parse_order_by(entries: Any) -> tuple[tuple[str, bool], ...]:
    """Return (field_name, is_descending) for each order_by entry.

    Handles both a plain '-field'/'field' string (Django's usual `order_by()`
    argument) and a Django `OrderBy` expression such as
    `F('field').desc(nulls_last=True)`, which `QuerySetGlue` uses so seek
    pagination has a consistent, backend-independent place to put NULLs.
    """
    parsed = []
    for entry in entries:
        if isinstance(entry, str):
            parsed.append((entry.lstrip('-'), entry.startswith('-')))
        else:
            expression = getattr(entry, 'expression', entry)
            name = getattr(expression, 'name', str(expression))
            parsed.append((name, bool(getattr(entry, 'descending', False))))
    return tuple(parsed)


@dataclass
class GlueSeekBatch:
    """One batch of rows returned by a GlueCollectionCursor.seek() call."""

    items: list[Any] = field(default_factory=list)
    has_next: bool = False
    next_seek_key: str | None = None


class GlueCollectionCursor:
    """Seek (keyset) pagination over an ordered Django QuerySet or an already-materialized list.

    Fetches one batch at a time by filtering for "rows after the last one already
    seen" instead of an OFFSET, so batch cost does not grow with how deep the
    client has scrolled, and no COUNT(*) is ever required to serve a batch --
    only `has_next` is exposed, derived from fetching one extra row past
    `batch_size` rather than from a separate count query.

    `objects` must already be ordered (see `QuerySetGlue._ensure_ordered`); this
    class always treats the model's pk as a forced, deduplicated final tiebreaker
    over whatever ordering is already present, so a non-unique explicit order_by
    (e.g. `order_by('species')`) still yields stable, non-overlapping batches.
    """

    def __init__(self, objects: models.QuerySet | Sequence[models.Model], batch_size: int) -> None:
        self.objects = objects
        self.batch_size = batch_size
        self._ordering = self._ordering_fields(objects)

    def seek(self, seek_key: str | None = None) -> GlueSeekBatch:
        objects = self.objects
        after = self._decode(seek_key, self._ordering)

        if after is not None:
            objects = self._rows_after(objects, after)

        # Fetch one extra row so `has_next` is known without a COUNT(*).
        if hasattr(objects, '__getitem__'):
            fetched = list(objects[: self.batch_size + 1])
        else:
            fetched = list(objects)[: self.batch_size + 1]

        has_next = len(fetched) > self.batch_size
        items = fetched[: self.batch_size]
        next_seek_key = self._encode(items[-1], self._ordering) if has_next and items else None

        return GlueSeekBatch(items=items, has_next=has_next, next_seek_key=next_seek_key)

    def _ordering_fields(self, objects: models.QuerySet | Sequence[models.Model]) -> tuple[str, ...]:
        """Field names (in effect) this collection is sorted by, with pk forced on as the final tiebreaker."""
        if hasattr(objects, 'model'):
            pk_name = objects.model._meta.pk.name
            order_fields = tuple(name for name, _ in parse_order_by(objects.query.order_by)) or (pk_name,)
        else:
            # Already-materialized list (e.g. a prefetched related set): no ORM
            # ordering to read, so pk is the only tiebreaker available -- batches
            # are seeked in the order the list was already given.
            pk_name = 'pk'
            order_fields = ()

        if pk_name not in order_fields:
            order_fields = (*order_fields, pk_name)

        return order_fields

    def _rows_after(
        self,
        objects: models.QuerySet | Sequence[models.Model],
        after: list[Any],
    ) -> models.QuerySet | list[models.Model]:
        if hasattr(objects, 'query'):
            return self._seek_filter(objects, after)

        # In-memory list: locate the seek-key row by matching every ordering
        # field, then take everything after it -- O(n) in the list's size,
        # same order of cost as the rest of the in-memory path already pays.
        for index, instance in enumerate(objects):
            if self._position_of(instance) == after:
                return list(objects[index + 1:])

        return list(objects)

    def _seek_filter(self, queryset: models.QuerySet, after: list[Any]) -> models.QuerySet:
        """Build the standard seek/keyset WHERE clause for a composite ordering.

        For ordering (a, b, pk) and a seek position (av, bv, pkv):
            a > av
            OR (a = av AND b > bv)
            OR (a = av AND b = bv AND pk > pkv)
        (each `>` becomes `<` for a field sorted descending.) Every row is
        included or excluded by comparison alone -- unlike OFFSET, no row before
        the seek position is ever scanned or counted.

        `QuerySetGlue` always orders nullable fields with `nulls_last=True`, so
        NULL sorts after every real value regardless of direction. That needs
        two adjustments here, following the same approach as the
        django-cursor-pagination package:

        - A seek value of `None` at a given depth means "the last row we saw
          was already in the NULL bucket for this field". Nothing sorts after
          NULL (nulls are last), so this depth contributes no comparison of
          its own -- only a deeper depth's equality prefix (`field=None`,
          which Django resolves to `field__isnull=True`) can find the next
          row, by staying inside the same NULL bucket and breaking the tie on
          a later field.
        - A non-null seek value's comparison (`field__gt`/`field__lt`) is
          extended with `OR field__isnull=True`, because SQL's `>`/`<` never
          match NULL on their own -- without this, seeking would never cross
          from the last real value into the trailing NULL bucket.
        """
        from django.db.models import Q  # noqa: PLC0415

        descending = {name for name, is_descending in parse_order_by(queryset.query.order_by) if is_descending}

        clauses = Q()
        for depth, (field, value) in enumerate(zip(self._ordering, after)):
            clause = Q()
            for earlier_field, earlier_value in zip(self._ordering[:depth], after[:depth]):
                clause &= Q(**{earlier_field: earlier_value})

            if value is None:
                continue

            lookup = f'{field}__lt' if field in descending else f'{field}__gt'
            clause &= (Q(**{lookup: value}) | Q(**{f'{field}__isnull': True}))
            clauses |= clause

        return queryset.filter(clauses)

    def _position_of(self, instance: models.Model) -> list[Any]:
        return [self._cursor_safe_value(getattr(instance, field)) for field in self._ordering]

    def _encode(self, instance: models.Model, ordering: tuple[str, ...]) -> str:
        position = [self._cursor_safe_value(getattr(instance, field)) for field in ordering]
        payload = json.dumps(position).encode('utf-8')
        return base64.urlsafe_b64encode(payload).decode('ascii')

    def _decode(self, seek_key: str | None, ordering: tuple[str, ...]) -> list[Any] | None:
        if seek_key is None:
            return None

        try:
            payload = base64.urlsafe_b64decode(seek_key.encode('ascii'))
            position = json.loads(payload.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            raise GlueQuerySetCursorValidationError(seek_key) from None

        if not isinstance(position, list) or len(position) != len(ordering):
            raise GlueQuerySetCursorValidationError(seek_key)

        return position

    @staticmethod
    def _cursor_safe_value(value: Any) -> Any:
        """Coerce a field value into something JSON-round-trippable and order-comparable."""
        if hasattr(value, 'isoformat'):
            return value.isoformat()
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return str(value)
