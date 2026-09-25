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


def test_template_override_wraps_the_component_in_a_full_page(client: Client) -> None:
    response = client.get(reverse('gorilla:component_card_page', kwargs={'start': 9}))

    assert response.status_code == 200
    html = response.content.decode()
    assert '<html' in html
    assert html.count('data-testid="counter-card"') == 1
    assert 'data-glue-address=' in html
    assert 'id="django-glue-context"' in html


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
