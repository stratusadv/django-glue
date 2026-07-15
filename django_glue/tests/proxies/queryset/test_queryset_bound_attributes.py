import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.settings')
django.setup()

from django.test import TestCase

from django_glue.access.access import GlueAccess
from django_glue.exceptions import GlueQuerySetFilterValidationError
from django_glue.tests.proxies.queryset.helpers import make_queryset_proxy
from test_project.gorilla.models import Gorilla, Skill


class GlueQuerySetProxyBoundAttributesTestCase(TestCase):
    def setUp(self):
        self.gorilla1 = Gorilla.objects.create(
            name='Gorilla 1',
            description='First gorilla',
            age=18,
            weight=200.0,
            height=1.8,
        )
        self.gorilla2 = Gorilla.objects.create(
            name='Important Gorilla',
            description='Second gorilla',
            age=25,
            weight=250.0,
            height=2.0,
        )
        self.gorilla3 = Gorilla.objects.create(
            name='Gorilla 3',
            description='Third gorilla',
            age=30,
            weight=300.0,
            height=2.2,
        )

    def test_query_with_params_populates_list_data(self):
        proxy = make_queryset_proxy(Gorilla.objects.all())

        proxy.query_with_params(request=None, filter=None, order_by=None, slice=None)

        self.assertEqual(len(proxy.state.list_data), 3)
        self.assertTrue(all('__policy__' in item for item in proxy.state.list_data))

    def test_query_with_params_includes_default_non_editable_fields(self):
        proxy = make_queryset_proxy(Gorilla.objects.filter(pk=self.gorilla1.pk))

        proxy.query_with_params(request=None, filter=None, order_by=None, slice=None)

        item = proxy.state.list_data[0]
        fields = proxy._custom_policy_details['included_fields']
        child_fields = item['__policy__']['subject_details']['included_fields']

        self.assertEqual(item['created_at'], self.gorilla1.created_at)
        self.assertEqual(item['updated_at'], self.gorilla1.updated_at)
        self.assertIn('created_at', fields)
        self.assertIn('created_at', child_fields)
        self.assertFalse(fields['created_at']['editable'])

    def test_query_with_params_serializes_m2m_values_as_choice_objects(self):
        skill = Skill.objects.create(name='Grappling')
        self.gorilla1.skills.add(skill)
        proxy = make_queryset_proxy(Gorilla.objects.filter(pk=self.gorilla1.pk))

        proxy.query_with_params(request=None, filter=None, order_by=None, slice=None)

        self.assertEqual(
            proxy.state.list_data[0]['skills'],
            [{'pk': skill.pk, '__str__': 'Grappling'}],
        )

    def test_query_with_params_respects_queryset_filter(self):
        proxy = make_queryset_proxy(Gorilla.objects.filter(age__gte=25))

        proxy.query_with_params(request=None, filter=None, order_by=None, slice=None)

        self.assertEqual(len(proxy.state.list_data), 2)
        self.assertTrue(all(item['age'] >= 25 for item in proxy.state.list_data))

    def test_query_with_params_applies_filter(self):
        proxy = make_queryset_proxy(Gorilla.objects.all())

        proxy.query_with_params(
            request=None,
            filter={'name__icontains': 'important'},
            order_by=None,
            slice=None,
        )

        self.assertEqual(len(proxy.state.list_data), 1)
        self.assertEqual(proxy.state.list_data[0]['name'], 'Important Gorilla')

    def test_query_with_params_applies_ordering(self):
        proxy = make_queryset_proxy(Gorilla.objects.all())

        proxy.query_with_params(request=None, filter=None, order_by='-age', slice=None)

        self.assertEqual([item['age'] for item in proxy.state.list_data], [30, 25, 18])

    def test_query_with_params_applies_slice(self):
        proxy = make_queryset_proxy(Gorilla.objects.all().order_by('age'))

        proxy.query_with_params(request=None, filter=None, order_by=None, slice={'start': 1, 'stop': 3})

        self.assertEqual([item['age'] for item in proxy.state.list_data], [25, 30])

    def test_query_with_params_rejects_disallowed_filter_field(self):
        proxy = make_queryset_proxy(Gorilla.objects.all(), fields=['name'])

        with self.assertRaises(GlueQuerySetFilterValidationError):
            proxy.query_with_params(
                request=None,
                filter={'weight__gte': 200},
                order_by=None,
                slice=None,
            )

    def test_new_returns_defaults_for_model_fields(self):
        proxy = make_queryset_proxy(Gorilla.objects.all())

        result = proxy.new(request=None)

        self.assertIsNone(result['id'])
        self.assertEqual(result['name'], '')
        self.assertEqual(result['age'], 18)
        self.assertEqual(result['skills'], [])
        self.assertIn('__policy__', result)
        self.assertEqual(result['__policy__']['name'], 'gorillas__None')
        self.assertEqual(result['__policy__']['subject_details']['target_pk'], None)
        self.assertIn('GlueModelInstanceProxy.save', result['__policy__']['bound_attributes'])

    def test_get_returns_model_dict_for_state_model(self):
        proxy = make_queryset_proxy(Gorilla.objects.all())
        proxy.state.model = self.gorilla1

        result = proxy.get(request=None)

        self.assertEqual(result['name'], 'Gorilla 1')

    def test_save_persists_state_model_form(self):
        proxy = make_queryset_proxy(Gorilla.objects.all(), access=GlueAccess.CHANGE)
        proxy.state.model = self.gorilla1
        proxy.state.form = proxy.state.form.__class__(
            data={
                'name': 'Updated',
                'description': 'Changed',
                'age': 19,
                'weight': 210.0,
                'height': 1.9,
                'rank_points': 0,
            },
            instance=self.gorilla1,
        )

        proxy.save(request=None)

        self.gorilla1.refresh_from_db()
        self.assertEqual(self.gorilla1.name, 'Updated')

    def test_delete_removes_state_model(self):
        proxy = make_queryset_proxy(Gorilla.objects.all(), access=GlueAccess.DELETE)
        proxy.state.model = self.gorilla1
        pk = self.gorilla1.pk

        proxy.delete(request=None)

        self.assertFalse(Gorilla.objects.filter(pk=pk).exists())

    def test_bound_attributes_have_expected_access(self):
        proxy = make_queryset_proxy(Gorilla.objects.all(), access=GlueAccess.DELETE)
        bound_attributes = proxy.discover_bound_attributes()

        self.assertEqual(bound_attributes['GlueQuerySetProxy.query_with_params'].required_access, GlueAccess.VIEW)
        self.assertEqual(bound_attributes['GlueQuerySetProxy.new'].required_access, GlueAccess.VIEW)
        self.assertEqual(bound_attributes['GlueQuerySetProxy.save'].required_access, GlueAccess.CHANGE)
        self.assertEqual(bound_attributes['GlueQuerySetProxy.delete'].required_access, GlueAccess.DELETE)
