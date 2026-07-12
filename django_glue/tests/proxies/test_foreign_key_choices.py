from django.test import TestCase

from django_glue.access.access import GlueAccess
from django_glue.proxies.model.instance.proxy import GlueModelInstanceProxy
from django_glue.proxies.queryset.proxy import GlueQuerySetProxy
from test_project.gorilla.models import Gorilla, Skill


def make_model_proxy(model, access=GlueAccess.VIEW):
    state, _ = GlueModelInstanceProxy._build_state(model)
    return GlueModelInstanceProxy(name='gorilla', namespace='model', access=access, state=state)


def make_queryset_proxy(queryset, access=GlueAccess.VIEW):
    model_instance = queryset.model()
    state, _ = GlueQuerySetProxy._build_state(model_instance)
    state.queryset = queryset
    return GlueQuerySetProxy(name='gorillas', namespace='querySet', access=access, state=state)


class ForeignKeyChoicesTestCase(TestCase):
    def setUp(self):
        self.skill1 = Skill.objects.create(name='Punch', description='Basic punch', difficulty=1, level=1)
        self.skill2 = Skill.objects.create(name='Kick', description='Basic kick', difficulty=2, level=1)
        self.gorilla = Gorilla.objects.create(
            name='Test Gorilla',
            description='Test',
            age=25,
            weight=350.0,
            height=1.8,
        )

    def test_foreign_key_choices_returns_choices_for_model_multiple_choice_field(self):
        proxy = make_queryset_proxy(Gorilla.objects.all())

        result = proxy.foreign_key_choices(request=None, field_name='skills')

        self.assertEqual(result, [
            {'pk': self.skill1.pk, '__str__': 'Punch'},
            {'pk': self.skill2.pk, '__str__': 'Kick'},
        ])

    def test_foreign_key_choices_returns_requested_extra_fields(self):
        proxy = make_queryset_proxy(Gorilla.objects.all())

        result = proxy.foreign_key_choices(
            request=None,
            field_name='skills',
            choice_fields=['difficulty'],
        )

        self.assertEqual(result, [
            {'pk': self.skill1.pk, '__str__': 'Punch', 'difficulty': 1},
            {'pk': self.skill2.pk, '__str__': 'Kick', 'difficulty': 2},
        ])

    def test_foreign_key_choices_returns_empty_for_non_model_choice_field(self):
        proxy = make_model_proxy(self.gorilla)

        result = proxy.foreign_key_choices(request=None, field_name='name')

        self.assertEqual(result, [])

    def test_foreign_key_choices_returns_empty_for_missing_field_name(self):
        proxy = make_model_proxy(self.gorilla)

        result = proxy.foreign_key_choices(request=None)

        self.assertEqual(result, [])

    def test_foreign_key_choices_is_registered_with_view_access(self):
        proxy = make_model_proxy(self.gorilla, access=GlueAccess.DELETE)

        bound_attributes = proxy.discover_bound_attributes()

        self.assertEqual(
            bound_attributes['GlueModelInstanceProxy.foreign_key_choices'].required_access,
            GlueAccess.VIEW,
        )
