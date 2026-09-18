from __future__ import annotations

from types import SimpleNamespace

import pytest
from django.test import TestCase

from django_glue.access import GlueAccess
from django_glue.glue.attributes import BoundGlueAttribute, GlueValueRole
from django_glue.glue.objects.django.form.object import FormGlue
from test_project.gorilla.forms import GorillaForm
from test_project.gorilla.models import Gorilla, Skill
from test_project.test_forms import ContactForm


def request_with_session(session_key='test-session'):
    return SimpleNamespace(session=SimpleNamespace(session_key=session_key), FILES={})


class FormIdentityTestCase(TestCase):
    def test_empty_file_field_initial_does_not_break_identity(self):
        glue_object = FormGlue(GorillaForm(instance=Gorilla()), name='new_gorilla_form', access=GlueAccess.CHANGE)
        glue_object.request = request_with_session()

        identity = glue_object.identity

        self.assertIn('profile_photo', identity['initial'])
        self.assertFalse(identity['initial']['profile_photo'])

    def test_many_to_many_initial_is_sorted_by_pk(self):
        gorilla = Gorilla.objects.create(name='Koko', age=20)
        second = Skill.objects.create(name='Swimming')
        first = Skill.objects.create(name='Climbing')
        gorilla.skills.add(second, first)
        glue_object = FormGlue(GorillaForm(instance=gorilla), name='gorilla_form', access=GlueAccess.CHANGE)
        glue_object.request = request_with_session()

        identity = glue_object.identity

        self.assertEqual(identity['initial']['skills'], sorted([first.pk, second.pk]))

    def test_explicit_editable_projection_controls_bound_data(self):
        form = ContactForm(initial={
            'name': 'Ada',
            'email': 'ada@example.com',
            'message': 'Hello',
            'priority': 'medium',
        })
        glue_object = FormGlue(
            form,
            name='contact',
            access=GlueAccess.CHANGE,
            editable=['name'],
        )

        glue_object._load_client_state({
            'name': {'value': 'Grace'},
            'email': {'value': 'attacker@example.com'},
        })

        assert glue_object.form.data['name'] == 'Grace'
        assert glue_object.form.data['email'] == 'ada@example.com'
        assert glue_object.form.data['message'] == 'Hello'

    def test_form_definitions_stage_only_editable_drafts(self):
        glue_object = FormGlue(
            ContactForm(initial={'name': 'Ada'}),
            name='contact',
            access=GlueAccess.CHANGE,
            editable=['name'],
        )
        name_definition = glue_object._attribute_registry.get('name')
        email_definition = glue_object._attribute_registry.get('email')

        assert name_definition is not None
        assert email_definition is not None
        assert name_definition.value_role == GlueValueRole.EDITABLE_STATE
        assert email_definition.value_role == GlueValueRole.DERIVED_OUTPUT

        name_attribute = BoundGlueAttribute(
            definition=name_definition,
            owner=glue_object,
        )
        email_attribute = BoundGlueAttribute(
            definition=email_definition,
            owner=glue_object,
        )
        name_attribute.apply_update('Draft')

        assert name_attribute.get() == 'Draft'
        assert glue_object.form['name'].value() == 'Ada'
        with pytest.raises(TypeError, match='does not accept client updates'):
            email_attribute.apply_update('attacker@example.com')

    def test_form_editable_projection_validates_its_boundary(self):
        with pytest.raises(ValueError, match='must be exposed'):
            FormGlue(
                ContactForm(),
                name='contact',
                access=GlueAccess.CHANGE,
                editable=['missing'],
            )

        form = ContactForm()
        form.fields['email'].disabled = True
        with pytest.raises(ValueError, match='cannot be editable'):
            FormGlue(
                form,
                name='contact',
                access=GlueAccess.CHANGE,
                editable=['email'],
            )

    def test_form_editable_projection_is_signed_and_revalidated(self):
        glue_object = FormGlue(
            ContactForm(initial={'name': 'Ada'}),
            name='contact',
            access=GlueAccess.CHANGE,
            editable=['name'],
        )
        glue_object.request = request_with_session()

        policy = glue_object.policy
        reconstructed = FormGlue._reconstruct_from_policy(policy)

        assert policy.identity['editable'] == ('name',)
        assert reconstructed.editable == ('name',)
