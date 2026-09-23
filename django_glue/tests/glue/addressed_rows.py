from __future__ import annotations

from typing import Any

from django_glue.glue.objects.django.queryset import QuerySetGlue


def addressed_row_entries(
    collection: QuerySetGlue,
    result: dict[str, Any],
) -> list[dict[str, Any]]:
    entries = {
        row.address: row.entry.model_dump()
        for row in (collection._row_glue(instance) for instance in collection.queryset)
    }
    return [entries[address] for address in result['items']]
