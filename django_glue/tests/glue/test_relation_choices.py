from __future__ import annotations

import json
from typing import Any

import pytest
from django.test import RequestFactory

from django_glue import Glue
from django_glue.access import GlueAccess
from django_glue.resolver.attribute_call.context import AddressedObjectEntry, AttributeCallBatchContext
from django_glue.resolver.attribute_call.resolver import GlueAttributeCallResolver
from django_glue.tests.conftest import MockSession
from test_project.fight.models import Fight
from test_project.gorilla.models import Gorilla, Skill

pytestmark = pytest.mark.django_db


def page_request():
    request = RequestFactory().get('/page/')
    request.session = MockSession()
    return request


def save(page, glue_object, updates: dict[str, Any]) -> dict[str, Any]:
    request = RequestFactory().post('/__dg__/callable_attribute/')
    request.session = page.session
    context = AttributeCallBatchContext.model_construct(
        request=request,
        entries=[AddressedObjectEntry.model_validate({
            'address': glue_object.address,
            'policy_token': glue_object.policy.token,
            'updates': updates,
            'call': {'attribute': 'save'},
        })],
        resolved_origins={},
    )
    response = GlueAttributeCallResolver()._resolve_json_response_from_context(context)
    return json.loads(response.content)['objects'][0]['result']


def fight_glue(page, fight, allowed):
    return Glue.model(
        page, 'fight', fight, access=GlueAccess.CHANGE,
        fields=('id', 'name', 'red_corner'),
        editable=['name', 'red_corner'],
        choices={'red_corner': Gorilla.objects.filter(pk=allowed.pk)},
    )


def gorilla_glue(page, gorilla, choices=None):
    return Glue.model(
        page, 'gorilla', gorilla, access=GlueAccess.CHANGE,
        fields=('id', 'name', 'skills'),
        editable=['skills'],
        choices=choices,
    )


def test_a_foreign_key_outside_its_choices_is_refused():
    allowed = Gorilla.objects.create(name='Allowed')
    forbidden = Gorilla.objects.create(name='Forbidden')
    fight = Fight.objects.create(name='F', description='d', red_corner=allowed, blue_corner=allowed)
    page = page_request()

    result = save(page, fight_glue(page, fight, allowed), {'red_corner': forbidden.pk})

    fight.refresh_from_db()
    assert result['success'] is False
    assert list(result['errors']) == ['red_corner']
    assert fight.red_corner_id == allowed.pk


def test_a_foreign_key_inside_its_choices_saves():
    first = Gorilla.objects.create(name='First')
    second = Gorilla.objects.create(name='Second')
    fight = Fight.objects.create(name='F', description='d', red_corner=first, blue_corner=first)
    page = page_request()

    result = save(page, fight_glue(page, fight, second), {'red_corner': second.pk})

    fight.refresh_from_db()
    assert result['success'] is True
    assert fight.red_corner_id == second.pk


def test_an_unchanged_foreign_key_outside_its_choices_still_saves():
    allowed = Gorilla.objects.create(name='Allowed')
    archived = Gorilla.objects.create(name='Archived')
    fight = Fight.objects.create(name='F', description='d', red_corner=archived, blue_corner=archived)
    page = page_request()

    result = save(page, fight_glue(page, fight, allowed), {'name': 'Renamed', 'red_corner': archived.pk})

    fight.refresh_from_db()
    assert result['success'] is True
    assert fight.name == 'Renamed'


def test_a_many_to_many_member_outside_its_choices_is_refused():
    allowed = Skill.objects.create(name='Allowed')
    forbidden = Skill.objects.create(name='Forbidden')
    gorilla = Gorilla.objects.create(name='G')
    page = page_request()
    glue_object = gorilla_glue(page, gorilla, {'skills': Skill.objects.filter(pk=allowed.pk)})

    result = save(page, glue_object, {'skills': [allowed.pk, forbidden.pk]})

    assert result['success'] is False
    assert list(result['errors']) == ['skills']
    assert list(gorilla.skills.all()) == []


def test_a_many_to_many_keeps_a_member_outside_its_choices_while_adding_one_inside():
    allowed = Skill.objects.create(name='Allowed')
    archived = Skill.objects.create(name='Archived')
    gorilla = Gorilla.objects.create(name='G')
    gorilla.skills.add(archived)
    page = page_request()
    glue_object = gorilla_glue(page, gorilla, {'skills': Skill.objects.filter(pk=allowed.pk)})

    result = save(page, glue_object, {'skills': [archived.pk, allowed.pk]})

    assert result['success'] is True
    assert set(gorilla.skills.values_list('pk', flat=True)) == {archived.pk, allowed.pk}


def test_a_many_to_many_member_that_does_not_exist_is_a_field_error():
    gorilla = Gorilla.objects.create(name='G')
    page = page_request()

    result = save(page, gorilla_glue(page, gorilla), {'skills': [999_999]})

    assert result['success'] is False
    assert list(result['errors']) == ['skills']


def test_a_queryset_row_refuses_a_foreign_key_outside_its_choices():
    allowed = Gorilla.objects.create(name='Allowed')
    forbidden = Gorilla.objects.create(name='Forbidden')
    fight = Fight.objects.create(name='F', description='d', red_corner=allowed, blue_corner=allowed)
    page = page_request()
    fights = Glue.queryset(
        page, 'fights', Fight.objects.all(), access=GlueAccess.CHANGE,
        fields=('id', 'name', 'red_corner'),
        editable=['red_corner'],
        choices={'red_corner': Gorilla.objects.filter(pk=allowed.pk)},
    )
    row = fights.get(pk=fight.pk)
    row.request = page

    result = save(page, row, {'red_corner': forbidden.pk})

    fight.refresh_from_db()
    assert result['success'] is False
    assert fight.red_corner_id == allowed.pk
