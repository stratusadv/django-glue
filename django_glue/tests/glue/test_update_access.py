from __future__ import annotations

import json
from typing import Any

import pytest
from django.test import RequestFactory

from django_glue import Glue
from django_glue.access import GlueAccess
from django_glue.glue.components import Component
from django_glue.glue.policy import GluePolicy
from django_glue.resolver.attribute_call.context import AddressedObjectEntry, AttributeCallBatchContext
from django_glue.resolver.attribute_call.resolver import GlueAttributeCallResolver
from django_glue.tests.conftest import MockSession
from test_project.gorilla.models import Gorilla

pytestmark = pytest.mark.django_db


class GuardedValueComponent(Component):
    template = 'glue_template_test.html'

    mode: str = Glue.attr('safe', editable=True, required_access=GlueAccess.CHANGE)

    @Glue.attr
    def read_mode(self) -> str:
        return self.mode


def page_request():
    request = RequestFactory().get('/page/')
    request.session = MockSession()
    return request


def send(page, address: str, token: str, attribute: str, updates: dict[str, Any]) -> dict[str, Any]:
    request = RequestFactory().post('/__dg__/callable_attribute/')
    request.session = page.session
    context = AttributeCallBatchContext.model_construct(
        request=request,
        entries=[AddressedObjectEntry.model_validate({
            'address': address,
            'policy_token': token,
            'updates': updates,
            'call': {'attribute': attribute},
        })],
        resolved_origins={},
    )
    response = GlueAttributeCallResolver()._resolve_json_response_from_context(context)
    return json.loads(response.content)['objects'][0]


def test_an_update_needs_the_access_its_value_requires():
    page = page_request()
    component = Glue.object(page, GuardedValueComponent())

    entry = send(page, component.address, component.policy.token, 'read_mode', {'mode': 'attacker'})

    assert entry['error']['code'] == 'not_authorized'


def test_an_update_with_the_access_its_value_requires_is_admitted():
    page = page_request()
    component = Glue.object(page, GuardedValueComponent(access=GlueAccess.CHANGE))

    entry = send(page, component.address, component.policy.token, 'read_mode', {'mode': 'edited'})

    assert entry['result'] == 'edited'


def test_an_add_draft_settles_to_view_with_nothing_editable_after_its_first_save():
    page = page_request()
    draft = Glue.model(page, 'draft', Gorilla(), access=GlueAccess.ADD, fields=('name', 'age'))

    entry = send(page, draft.address, draft.policy.token, 'save', {'name': 'New', 'age': 5})

    successor = GluePolicy.from_token(entry['policy_token'])
    assert entry['result']['success'] is True
    assert successor.access == GlueAccess.VIEW
    assert successor.identity['target_pk'] == Gorilla.objects.get(name='New').pk


def test_a_saved_add_draft_refuses_an_edit_through_a_view_method():
    page = page_request()
    draft = Glue.model(page, 'draft', Gorilla(), access=GlueAccess.ADD, fields=('name', 'age'))
    saved = send(page, draft.address, draft.policy.token, 'save', {'name': 'New', 'age': 5})

    entry = send(page, draft.address, saved['policy_token'], 'something', {'name': 'Edited'})

    assert entry['error']['code'] == 'invalid_updates'
    assert Gorilla.objects.filter(name='Edited').exists() is False


def test_an_add_model_of_a_saved_row_has_nothing_editable():
    gorilla = Gorilla.objects.create(name='Existing', age=3, weight=100.0, height=1.5)
    page = page_request()

    glue_object = Glue.model(page, 'gorilla', gorilla, access=GlueAccess.ADD, fields=('name', 'age'))

    assert glue_object.editable == ()
