from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, ClassVar

import pytest

from django_glue import Glue
from django_glue.exceptions import GlueAnnotationError
from django_glue.glue.attributes import GlueAttributeCollector
from django_glue.glue.components import Component

if TYPE_CHECKING:
    # Imported only for type checkers, as an app does for a ClassVar's type: it doesn't exist at runtime.
    from test_project.gorilla.models import Gorilla as TypeCheckingOnly


def collected(owner: type, path: str):
    return next(attribute for attribute in GlueAttributeCollector.collect(owner) if attribute.path == path)


def test_a_classvar_typed_only_for_type_checkers_does_not_stop_a_component(mock_request) -> None:
    class RosterComponent(Component):
        template = 'glue_template_test.html'
        model_class: ClassVar[type[TypeCheckingOnly]]

        count: int = Glue.attr(parameter=True)

    component = Glue.object(mock_request, RosterComponent(count='3'))

    # The parameter's own annotation still types it.
    assert component.count == 3


def test_a_classvar_on_a_base_class_does_not_stop_its_subclasses(mock_request) -> None:
    class BaseRosterComponent(Component):
        template = 'glue_template_test.html'
        model_class: ClassVar[type[TypeCheckingOnly]]

    class RosterComponent(BaseRosterComponent):
        count: int = Glue.attr(parameter=True)

    assert Glue.object(mock_request, RosterComponent(count='4')).count == 4


def test_an_unrelated_annotation_no_longer_costs_the_attributes_their_types() -> None:
    class FightCardComponent(Component):
        template = 'glue_template_test.html'
        note: TypeCheckingOnly
        fight_date: datetime.date = Glue.attr(datetime.date(2026, 11, 23))

    assert collected(FightCardComponent, 'fight_date').serializer is not None


def test_a_parameter_whose_annotation_cant_be_resolved_says_which() -> None:
    with pytest.raises(GlueAnnotationError, match=r"BrokenComponent\.count's annotation .*TypeCheckingOnly"):
        class BrokenComponent(Component):
            template = 'glue_template_test.html'
            count: TypeCheckingOnly = Glue.attr(parameter=True)
