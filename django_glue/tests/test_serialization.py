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


def test_a_type_hint_builds_its_adapter_once() -> None:
    raw = {'start': '2026-09-01', 'end': '2026-09-30'}

    with mock.patch.object(serialization, 'TypeAdapter', wraps=TypeAdapter) as built:
        window = glue_serializer_registry.resolve(ReportWindow).load(raw)
        glue_serializer_registry.resolve(ReportWindow).dump(window)
        glue_serializer_registry.resolve(ReportWindow).restore(raw)

    assert window == ReportWindow(start=datetime.date(2026, 9, 1), end=datetime.date(2026, 9, 30))
    assert built.call_count == 1


def test_a_type_hint_dumps_what_it_loads() -> None:
    serializer = glue_serializer_registry.resolve(ReportWindow)
    raw = {'start': '2026-09-01', 'end': '2026-09-30'}

    assert serializer.dump(serializer.load(raw)) == raw


def test_an_undeclared_value_crosses_as_it_is() -> None:
    serializer = glue_serializer_registry.resolve(None)

    assert serializer.load('7') == '7'
    assert serializer.restore('7') == '7'
    assert serializer.dump('7') == '7'
