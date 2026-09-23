from __future__ import annotations

from typing import TYPE_CHECKING

from django.http import HttpRequest

from django_glue import Glue
from django_glue.access import GlueAccess
from django_glue.glue.base import BaseGlue
from django_glue.glue.policy import GluePolicy
from django_glue.tests.glue.test_callable_parameters import call_context

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from django_glue.glue.objects.django.model.object import ModelGlue


class TypeCheckingReturnGlue(BaseGlue):
    namespace = 'typeCheckingReturn'

    def __init__(self) -> None:
        super().__init__(access=GlueAccess.CHANGE)

    @Glue.attr
    def new_entry(self, request: HttpRequest) -> ModelGlue:
        from test_project.gorilla.models import Gorilla  # noqa: PLC0415

        return Glue.model(Gorilla(name='New'), fields=['name'], access=GlueAccess.CHANGE)

    @Glue.attr
    def maybe_entry(self) -> ModelGlue | None:
        return None

    @Glue.attr
    def plain_rows(self) -> QuerySet:
        return []

    @classmethod
    def _reconstruct_from_policy(cls, policy: GluePolicy) -> TypeCheckingReturnGlue:
        _ = policy
        return cls()


def test_type_checking_only_glue_return_annotation_introduces_the_result(mock_request, db) -> None:
    del db
    glue_object = Glue.object(mock_request, TypeCheckingReturnGlue())

    assert glue_object.get_static_data()['callables']['new_entry']['returns_glue'] is True
    entry, introduced = glue_object.process_attribute_call(
        call_context(glue_object, 'new_entry'),
    )

    assert [introduced_entry['address'] for introduced_entry in introduced] == [entry['result']]


def test_type_checking_only_nullable_glue_return_accepts_none(mock_request) -> None:
    glue_object = Glue.object(mock_request, TypeCheckingReturnGlue())

    entry, introduced = glue_object.process_attribute_call(
        call_context(glue_object, 'maybe_entry'),
    )

    assert glue_object.get_static_data()['callables']['maybe_entry']['returns_glue'] is True
    assert entry['result'] is None
    assert introduced == []


def test_unresolvable_non_glue_return_annotation_stays_an_ordinary_result(mock_request) -> None:
    glue_object = Glue.object(mock_request, TypeCheckingReturnGlue())

    entry, _introduced = glue_object.process_attribute_call(
        call_context(glue_object, 'plain_rows'),
    )

    assert glue_object.get_static_data()['callables']['plain_rows']['returns_glue'] is False
    assert entry['result'] == []
