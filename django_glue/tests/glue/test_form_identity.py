from types import SimpleNamespace

from django.test import TestCase

from django_glue.access import GlueAccess
from django_glue.glue.objects.django.form.object import FormGlue
from test_project.gorilla.forms import GorillaForm
from test_project.gorilla.models import Gorilla, Skill


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
