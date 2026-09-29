from __future__ import annotations

import datetime
from dataclasses import dataclass
from unittest import mock

from pydantic import TypeAdapter

from django_glue import serialization
from django_glue.serialization import glue_serializer_registry


@dataclass(frozen=True)
class ReportWindow:
    start: datetime.date
    end: datetime.date


def test_an_annotation_builds_its_adapter_once() -> None:
    raw = {'start': '2026-09-01', 'end': '2026-09-30'}

    with mock.patch.object(serialization, 'TypeAdapter', wraps=TypeAdapter) as built:
        window = glue_serializer_registry.coerce(raw, ReportWindow)
        glue_serializer_registry.encode(window, ReportWindow)
        glue_serializer_registry.decode(raw, ReportWindow)

    assert window == ReportWindow(start=datetime.date(2026, 9, 1), end=datetime.date(2026, 9, 30))
    assert built.call_count == 1
