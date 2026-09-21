"""
Focused tests for the ADD capability (state-model.md §3-§4, ADR 009).

Covers the phase-3 permission foundation beyond the enum: QuerySetGlue.new()
draft creation, row-vs-draft access, target-aware save admission on models
and model forms, and the first-save settlement of a draft to the collection's
persisted-row access.
"""

from __future__ import annotations

import json
import os

import django
from django.test import RequestFactory, TestCase

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.settings')
django.setup()

from django_glue.access import GlueAccess
from django_glue.glue import FormGlue, ModelGlue, QuerySetGlue
from django_glue.glue.policy import GluePolicy
from django_glue.resolver.attribute_call.resolver import GlueAttributeCallResolver
from django_glue.tests.conftest import MockSession
from test_project.gorilla.forms import GorillaForm
from test_project.gorilla.models import Gorilla

glue_attribute_call_view = GlueAttributeCallResolver.as_view()


class _AttributeRequestMixin:
    """Shared HTTP plumbing for driving the attribute-call resolver."""

    def setUp(self):
        self.factory = RequestFactory()
        self.session = MockSession(session_key='session-1')

    def attribute_request(self, object_name, policy, attribute, kwargs=None, updates=None):
        request = self.factory.post(
            f'/__dg__/callable_attribute/{object_name}/{attribute}/',
            data={
                'policy_token': policy.token,
                'attribute': attribute,
                'kwargs': json.dumps(kwargs or {}, default=str),
                **({'updates': json.dumps(updates, default=str)} if updates is not None else {}),
            },
        )
        request.resolver_match = type(
            'ResolverMatch',
            (),
            {'kwargs': {'object_name': object_name, 'attribute_name': attribute}},
        )()
        request.session = self.session
        request.user = 'TestUser'
        return request

    def call(self, object_name, policy, attribute, kwargs=None, updates=None):
        request = self.attribute_request(
            object_name,
            policy,
            attribute,
            kwargs=kwargs,
            updates=updates,
        )
        return glue_attribute_call_view(
            request,
            object_name=object_name,
            attribute_name=attribute,
        )

    def request_context(self):
        return type('Request', (), {'session': self.session, 'FILES': {}})()

    @staticmethod
    def decode(token):
        return GluePolicy.from_token(token)


class GlueAddQuerysetCreationTestCase(_AttributeRequestMixin, TestCase):
    """QuerySetGlue.new() draft access and row-vs-draft access."""

    def setUp(self):
        super().setUp()
        self.gorilla = Gorilla.objects.create(
            name='Koko',
            description='Leader',
            age=18,
            weight=200.0,
            height=1.8,
        )

    def bound_queryset(self, access, name='gorillas', fields=('name', 'age')):
        glue_object = QuerySetGlue(
            Gorilla.objects.all(),
            name=name,
            access=access,
            fields=fields,
        )
        glue_object.request = self.request_context()
        return glue_object

    def test_view_queryset_denies_new(self):
        """new() requires ADD, so a VIEW queryset cannot create a draft."""
        glue_object = self.bound_queryset(GlueAccess.VIEW)

        response = self.call('gorillas', glue_object.policy, 'new', kwargs={'initial': {}})

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertEqual(data['result']['error']['code'], 'proxy_access_denied')

    def test_add_queryset_new_returns_unsaved_add_draft(self):
        """new(initial) on an ADD queryset introduces an unsaved ADD draft
        without persisting anything."""
        glue_object = self.bound_queryset(GlueAccess.ADD)

        response = self.call(
            'gorillas',
            glue_object.policy,
            'new',
            kwargs={'initial': {'name': 'New', 'age': 5}},
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        draft = self.decode(data['result']['policy_token'])
        self.assertEqual(draft.name, 'gorillas.None')
        self.assertEqual(draft.access, GlueAccess.ADD)
        self.assertIsNone(draft.identity['target_pk'])
        self.assertFalse(Gorilla.objects.filter(name='New').exists())

    def test_new_initial_admitted_only_against_signed_editable(self):
        """new(initial) rejects keys outside the signed editable projection —
        ADD grants no mass-assignment expansion."""
        glue_object = self.bound_queryset(GlueAccess.ADD)

        response = self.call(
            'gorillas',
            glue_object.policy,
            'new',
            kwargs={'initial': {'description': 'sneaky'}},
        )

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEqual(data['result']['error']['code'], 'invalid_kwargs')

    def test_existing_row_of_add_queryset_is_view(self):
        """Persisted rows of an ADD-only queryset are signed VIEW, not ADD."""
        glue_object = self.bound_queryset(GlueAccess.ADD)

        payload = glue_object._build_child_model_payload(self.gorilla)
        row = self.decode(payload['policy_token'])

        self.assertEqual(row.name, f'gorillas.{self.gorilla.pk}')
        self.assertEqual(row.access, GlueAccess.VIEW)
        self.assertEqual(row.identity['target_pk'], self.gorilla.pk)

    def test_persisted_row_of_add_queryset_save_is_denied(self):
        """A persisted VIEW row of an ADD queryset cannot be saved: saving a
        signed persisted target requires CHANGE."""
        glue_object = self.bound_queryset(GlueAccess.ADD)
        payload = glue_object._build_child_model_payload(self.gorilla)
        row = self.decode(payload['policy_token'])

        response = self.call(
            row.name,
            row,
            'save',
            updates={'name': 'Hacked'},
        )

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertEqual(data['result']['error']['code'], 'proxy_access_denied')
        self.gorilla.refresh_from_db()
        self.assertEqual(self.gorilla.name, 'Koko')

    def test_add_draft_first_save_creates_and_settles_same_address_to_view(self):
        """A draft's first save atomically persists it, keeps the same address,
        and settles the successor to the collection's persisted-row access
        (VIEW for an ADD queryset)."""
        glue_object = self.bound_queryset(GlueAccess.ADD)
        new_response = self.call(
            'gorillas',
            glue_object.policy,
            'new',
            kwargs={'initial': {'name': 'New', 'age': 5}},
        )
        draft = self.decode(json.loads(new_response.content)['result']['policy_token'])

        save_response = self.call(
            draft.name,
            draft,
            'save',
            updates={'name': 'New', 'age': 5},
        )

        self.assertEqual(save_response.status_code, 200)
        saved = Gorilla.objects.get(name='New')
        successor = self.decode(json.loads(save_response.content)['policy_token'])
        self.assertEqual(successor.name, 'gorillas.None')
        self.assertEqual(successor.access, GlueAccess.VIEW)
        self.assertEqual(successor.identity['target_pk'], saved.pk)

        # The settled row is a persisted VIEW row: further mutation requires
        # CHANGE and must be denied through the same (unchanged) address.
        second = self.call(
            successor.name,
            successor,
            'save',
            updates={'name': 'Edited'},
        )
        self.assertEqual(second.status_code, 403)
        saved.refresh_from_db()
        self.assertEqual(saved.name, 'New')

    def test_change_draft_save_settles_to_change_and_stays_editable(self):
        """For a CHANGE collection, the draft settles to CHANGE after first
        save, so save-then-edit keeps working on the same address."""
        glue_object = self.bound_queryset(GlueAccess.CHANGE)
        new_response = self.call(
            'gorillas',
            glue_object.policy,
            'new',
            kwargs={'initial': {'name': 'New', 'age': 5}},
        )
        draft = self.decode(json.loads(new_response.content)['result']['policy_token'])
        self.assertEqual(draft.access, GlueAccess.ADD)

        save_response = self.call(
            draft.name,
            draft,
            'save',
            updates={'name': 'New', 'age': 5},
        )

        self.assertEqual(save_response.status_code, 200)
        successor = self.decode(json.loads(save_response.content)['policy_token'])
        self.assertEqual(successor.name, 'gorillas.None')
        self.assertEqual(successor.access, GlueAccess.CHANGE)

        edit_response = self.call(
            successor.name,
            successor,
            'save',
            updates={'name': 'Edited', 'age': 6},
        )
        self.assertEqual(edit_response.status_code, 200)
        self.assertEqual(Gorilla.objects.get(name='Edited').age, 6)

    def test_editable_projection_is_gated_at_add(self):
        """The signed editable projection survives at ADD (so new(initial) has
        a projection to admit against) and stays empty at VIEW."""
        qs_add = QuerySetGlue(
            Gorilla.objects.all(), name='g', access=GlueAccess.ADD, fields=['name', 'age']
        )
        qs_view = QuerySetGlue(
            Gorilla.objects.all(), name='g', access=GlueAccess.VIEW, fields=['name', 'age']
        )
        model_add = ModelGlue(
            Gorilla(), name='m', access=GlueAccess.ADD, fields=['name', 'age']
        )
        model_view = ModelGlue(
            self.gorilla, name='m', access=GlueAccess.VIEW, fields=['name', 'age']
        )

        self.assertEqual(qs_add.editable, ('name', 'age'))
        self.assertEqual(qs_view.editable, ())
        self.assertEqual(model_add.editable, ('name', 'age'))
        self.assertEqual(model_view.editable, ())


class GlueModelSaveAdmissionTestCase(_AttributeRequestMixin, TestCase):
    """ModelGlue.save() chooses required access from the signed target identity."""

    def setUp(self):
        super().setUp()
        self.gorilla = Gorilla.objects.create(
            name='Koko',
            description='Leader',
            age=18,
            weight=200.0,
            height=1.8,
        )

    def bound_model(self, instance, access, name='gorilla', fields=('name', 'age')):
        glue_object = ModelGlue(instance, name=name, access=access, fields=fields)
        glue_object.request = self.request_context()
        return glue_object

    def test_unsaved_model_at_add_saves_only_while_unsaved(self):
        """Saving an unsaved model requires ADD; once persisted that same
        address requires CHANGE, so a create-only model cannot mutate its
        own saved row."""
        glue_object = self.bound_model(Gorilla(), GlueAccess.ADD)

        response = self.call(
            'gorilla',
            glue_object.policy,
            'save',
            updates={'name': 'Fresh', 'age': 5},
        )

        self.assertEqual(response.status_code, 200)
        saved = Gorilla.objects.get(name='Fresh')
        successor = self.decode(json.loads(response.content)['policy_token'])
        self.assertEqual(successor.identity['target_pk'], saved.pk)

        second = self.call(
            'gorilla',
            successor,
            'save',
            updates={'name': 'Mutated', 'age': 5},
        )
        self.assertEqual(second.status_code, 403)
        saved.refresh_from_db()
        self.assertEqual(saved.name, 'Fresh')

    def test_persisted_model_at_add_save_is_denied(self):
        """A create-only (ADD) model cannot save a persisted target, which
        requires CHANGE."""
        glue_object = self.bound_model(self.gorilla, GlueAccess.ADD)

        response = self.call(
            'gorilla',
            glue_object.policy,
            'save',
            updates={'name': 'Mutated'},
        )

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertEqual(data['result']['error']['code'], 'proxy_access_denied')
        self.gorilla.refresh_from_db()
        self.assertEqual(self.gorilla.name, 'Koko')

    def test_persisted_model_at_change_still_saves(self):
        """A persisted CHANGE model still saves (unchanged legacy behavior)."""
        glue_object = self.bound_model(self.gorilla, GlueAccess.CHANGE)

        response = self.call(
            'gorilla',
            glue_object.policy,
            'save',
            updates={'name': 'Updated'},
        )

        self.assertEqual(response.status_code, 200)
        self.gorilla.refresh_from_db()
        self.assertEqual(self.gorilla.name, 'Updated')


class GlueFormSaveAdmissionTestCase(_AttributeRequestMixin, TestCase):
    """FormGlue.save() on a model form chooses required access from the
    signed target identity (state-model.md §3)."""

    def setUp(self):
        super().setUp()
        self.gorilla = Gorilla.objects.create(
            name='Koko',
            description='Leader',
            age=18,
            weight=200.0,
            height=1.8,
        )

    def bound_form(self, form, access, name='gorilla_form'):
        glue_object = FormGlue(form, name=name, access=access)
        glue_object.request = self.request_context()
        return glue_object

    def test_unsaved_model_form_at_add_saves(self):
        """Saving a model form bound to an unsaved instance requires ADD."""
        glue_object = self.bound_form(GorillaForm(instance=Gorilla()), GlueAccess.ADD)

        response = self.call(
            'gorilla_form',
            glue_object.policy,
            'save',
            updates={
                'name': 'Filo',
                'age': 5,
                'weight': 200.0,
                'height': 1.8,
                'rank_points': 0,
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['result']['valid'])
        self.assertTrue(Gorilla.objects.filter(name='Filo').exists())

    def test_persisted_model_form_at_add_save_is_denied(self):
        """A create-only (ADD) model form cannot save a persisted target,
        which requires CHANGE."""
        glue_object = self.bound_form(
            GorillaForm(instance=self.gorilla),
            GlueAccess.ADD,
        )

        response = self.call(
            'gorilla_form',
            glue_object.policy,
            'save',
            updates={
                'name': 'Mutated',
                'age': 18,
                'weight': 200.0,
                'height': 1.8,
                'rank_points': 0,
            },
        )

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertEqual(data['result']['error']['code'], 'proxy_access_denied')
        self.gorilla.refresh_from_db()
        self.assertEqual(self.gorilla.name, 'Koko')
