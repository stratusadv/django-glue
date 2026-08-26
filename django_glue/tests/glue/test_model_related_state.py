from types import SimpleNamespace

from django.test import TestCase

from django_glue.access import GlueAccess
from django_glue.glue.objects.django.model.object import ModelGlue
from test_project.fight.models import Fight
from test_project.gorilla.models import Gorilla


def request_with_session(session_key='test-session'):
    return SimpleNamespace(session=SimpleNamespace(session_key=session_key), FILES={})


class RelatedStateTestCase(TestCase):
    def setUp(self):
        self.alpha = Gorilla.objects.create(name='Alpha', age=12)
        self.beta = Gorilla.objects.create(name='Beta', age=24)
        self.fight = Fight.objects.create(name='Bout', red_corner=self.alpha, blue_corner=self.beta)

    def _glue(self):
        glue_object = ModelGlue(self.fight, name='fight', access=GlueAccess.CHANGE, fields=['name', 'red_corner', 'blue_corner'])
        glue_object.request = request_with_session()

        return glue_object

    def test_nested_related_state_keeps_the_foreign_key(self):
        glue_object = self._glue()
        state = glue_object.state

        self.assertEqual(state['red_corner_id']['value'], self.alpha.pk)
        self.assertNotIn('value', state['red_corner'])

        glue_object._load_client_state(state)

        self.assertEqual(glue_object.instance.red_corner_id, self.alpha.pk)
        self.assertEqual(glue_object.state['red_corner_id']['value'], self.alpha.pk)

    def test_attname_state_wins_over_nested_state(self):
        glue_object = self._glue()
        state = glue_object.state
        state['red_corner_id'] = {'value': self.beta.pk, 'errors': []}

        glue_object._load_client_state(state)

        self.assertEqual(glue_object.instance.red_corner_id, self.beta.pk)

    def test_nested_pk_is_used_without_attname_state(self):
        glue_object = self._glue()
        state = glue_object.state
        del state['red_corner_id']
        state['red_corner']['id'] = {'value': self.beta.pk, 'errors': []}

        glue_object._load_client_state(state)

        self.assertEqual(glue_object.instance.red_corner_id, self.beta.pk)

    def test_plain_value_state_still_applies(self):
        glue_object = self._glue()

        glue_object._load_client_state({'red_corner': {'value': self.beta.pk}})

        self.assertEqual(glue_object.instance.red_corner_id, self.beta.pk)

    def test_null_value_clears_the_relation(self):
        glue_object = self._glue()

        glue_object._load_client_state({'blue_corner_id': {'value': None}})

        self.assertIsNone(glue_object.instance.blue_corner_id)
