from __future__ import annotations

import json
import re
from html import unescape
from typing import TYPE_CHECKING

import pytest
from django.contrib.auth import get_user_model
from django.template import Context, Template
from django.urls import reverse

from django_glue.exceptions import GlueComponentKeyError
from django_glue.glue.policy import GluePolicy
from test_project.gorilla.components import (
    CounterCardComponent,
    LaidOutCounterCardComponent,
)

if TYPE_CHECKING:
    from django.test import Client


pytestmark = pytest.mark.django_db


def test_component_url_renders_an_addressed_fragment_from_url_parameters(client: Client) -> None:
    response = client.get(reverse('gorilla:component_card_fragment', kwargs={'start': 7}))

    assert response.status_code == 200
    html = response.content.decode()
    assert 'data-testid="counter-card"' in html
    assert 'data-glue-address=' in html
    match = re.search(r'data-glue-objects="([^"]+)"', html)
    assert match is not None
    entries = json.loads(unescape(match.group(1)))
    policy = GluePolicy.from_token(entries[0]['policy_token'])
    assert policy.identity['parameters']['start'] == 7
    assert policy.state_snapshot['count'] == 7
    assert '<html' not in html


def test_view_template_renders_the_component_inside_a_full_page(client: Client) -> None:
    response = client.get(reverse('gorilla:component_card_page', kwargs={'start': 9}))

    assert response.status_code == 200
    html = response.content.decode()
    assert '<html' in html
    assert html.count('data-testid="counter-card"') == 1
    assert 'data-glue-address=' in html
    assert 'id="django-glue-context"' in html


def test_view_template_class_attribute_is_the_default_view_template(client: Client) -> None:
    response = client.get(reverse('gorilla:component_laid_out_card', kwargs={'start': 9}))

    assert response.status_code == 200
    template_names = [template.name for template in response.templates]
    assert 'gorilla/page/component_card_page.html' in template_names
    assert response.content.decode().count('data-testid="counter-card"') == 1


def test_as_view_view_template_overrides_the_class_attribute(client: Client) -> None:
    response = client.get(reverse('gorilla:component_laid_out_card_alt', kwargs={'start': 9}))

    assert response.status_code == 200
    template_names = [template.name for template in response.templates]
    assert 'gorilla/page/component_card_alt_page.html' in template_names
    assert 'gorilla/page/component_card_page.html' not in template_names
    assert 'data-testid="alt-layout"' in response.content.decode()


def test_bare_component_tag_requires_a_component_view() -> None:
    template = Template('{% load django_glue %}{% glue_component %}')

    with pytest.raises(GlueComponentKeyError, match='component view'):
        template.render(Context({'component': object()}))


def test_component_url_rejects_post(client: Client) -> None:
    response = client.post(reverse('gorilla:component_card_fragment', kwargs={'start': 7}))

    assert response.status_code == 405


def test_component_authorization_denial_returns_forbidden_page(client: Client) -> None:
    response = client.get(reverse('gorilla:component_protected_card', kwargs={'start': 7}))

    assert response.status_code == 403


def test_component_authorization_allows_authenticated_page(client: Client) -> None:
    user = get_user_model().objects.create_user(username='component-view-user')
    client.force_login(user)

    response = client.get(reverse('gorilla:component_protected_card', kwargs={'start': 7}))

    assert response.status_code == 200
    assert 'data-testid="counter-card"' in response.content.decode()


def test_unnamed_component_is_named_after_its_class() -> None:
    first = CounterCardComponent(start=1)
    second = CounterCardComponent(start=2)

    assert first.name.startswith('counter_card_')
    assert first.name == second.name
    assert LaidOutCounterCardComponent(start=1).name.startswith('laid_out_counter_card_')


def test_defining_the_renamed_layout_template_fails_at_class_definition() -> None:
    with pytest.raises(TypeError, match='view_template'):
        class LegacyLaidOutComponent(CounterCardComponent):
            layout_template = 'gorilla/page/component_card_page.html'


def test_defining_the_removed_get_view_kwargs_fails_at_class_definition() -> None:
    with pytest.raises(TypeError, match='__post_init__'):
        class LegacyRequestCardComponent(CounterCardComponent):
            @classmethod
            def get_view_kwargs(cls, request, **url_kwargs):
                return url_kwargs


def test_a_url_capture_overrides_the_same_as_view_parameter(mock_request) -> None:
    response = CounterCardComponent.as_view(start=1)(mock_request, start=13)

    assert _root_policy(response.content.decode()).identity['parameters']['start'] == 13


def _root_policy(html: str) -> GluePolicy:
    match = re.search(r'data-glue-objects="([^"]+)"', html)
    assert match is not None
    return GluePolicy.from_token(json.loads(unescape(match.group(1)))[0]['policy_token'])


def test_component_can_derive_view_parameters_and_access_from_request(client: Client) -> None:
    response = client.get(reverse('gorilla:component_request_card'), {'start': '11'})

    assert response.status_code == 200
    html = response.content.decode()
    match = re.search(r'data-glue-objects="([^"]+)"', html)
    assert match is not None
    entries = json.loads(unescape(match.group(1)))
    policy = GluePolicy.from_token(entries[0]['policy_token'])
    assert policy.identity['parameters']['start'] == 11
    assert policy.access == 'change'
