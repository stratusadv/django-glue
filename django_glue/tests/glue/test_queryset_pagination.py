from __future__ import annotations

from types import SimpleNamespace

from django.test import TestCase, override_settings

from django_glue import ALL_FIELDS
from django_glue.access import GlueAccess
from django_glue.exceptions import GlueQuerySetPageValidationError
from django_glue.glue.objects.django.queryset import QuerySetGlue
from django_glue.glue.policy import GluePolicy
from django_glue.glue.loading import LoadingStrategy
from django_glue.glue.attributes.django.model.related_set import RelatedSetFieldAttribute
from django_glue.glue.objects.django.model.object import ModelGlue
from test_project.fight.models import Fight
from test_project.gorilla.models import Gorilla


def request_with_session(session_key='test-session'):
    return SimpleNamespace(session=SimpleNamespace(session_key=session_key), FILES={})


def build_glue(queryset=None, **kwargs):
    glue_object = QuerySetGlue(
        Gorilla.objects.all() if queryset is None else queryset,
        name='gorillas',
        access=GlueAccess.VIEW,
        fields=['id', 'name'],
        **kwargs,
    )
    glue_object.request = request_with_session()
    glue_object.policy

    return glue_object


class QuerySetPaginationTestCase(TestCase):
    def setUp(self):
        for index in range(7):
            Gorilla.objects.create(name=f'Gorilla {index:02d}', age=index, weight=100.0, height=1.5)

    def _names(self, result):
        return [row['state']['name']['value'] for row in result['items']]

    def test_page_size_defaults_to_setting(self):
        with override_settings(DJANGO_GLUE_QUERYSET_PAGE_SIZE=3):
            glue_object = build_glue()

        self.assertEqual(glue_object.page_size, 3)

    def test_page_size_none_disables_pagination(self):
        glue_object = build_glue(page_size=None)

        result = glue_object.query_with_params()

        self.assertEqual(len(result['items']), 7)
        self.assertEqual(result['total'], 7)
        self.assertEqual(result['page'], 1)
        self.assertIsNone(result['page_size'])
        self.assertEqual(result['page_count'], 1)

    def test_page_past_end_of_unpaginated_queryset_is_empty(self):
        glue_object = build_glue(page_size=None)

        result = glue_object.query_with_params(page=2)

        self.assertEqual(result['items'], [])
        self.assertEqual(result['total'], 7)
        self.assertEqual(result['page'], 2)
        self.assertEqual(result['page_count'], 1)

    def test_invalid_page_size_raises(self):
        for page_size in (0, -1, True, '5', 2.5):
            with self.assertRaises(ValueError):
                build_glue(page_size=page_size)

    def test_first_page_is_bounded_and_carries_totals(self):
        glue_object = build_glue(page_size=3)

        result = glue_object.query_with_params()

        self.assertEqual(self._names(result), ['Gorilla 00', 'Gorilla 01', 'Gorilla 02'])
        self.assertEqual(result['total'], 7)
        self.assertEqual(result['page'], 1)
        self.assertEqual(result['page_size'], 3)
        self.assertEqual(result['page_count'], 3)

    def test_last_page_is_partial(self):
        glue_object = build_glue(page_size=3)

        result = glue_object.query_with_params(page=3)

        self.assertEqual(self._names(result), ['Gorilla 06'])
        self.assertEqual(result['page'], 3)
        self.assertEqual(result['page_count'], 3)

    def test_page_past_end_is_empty_with_totals(self):
        glue_object = build_glue(page_size=3)

        result = glue_object.query_with_params(page=9)

        self.assertEqual(result['items'], [])
        self.assertEqual(result['total'], 7)
        self.assertEqual(result['page'], 9)
        self.assertEqual(result['page_count'], 3)

    def test_empty_queryset_has_one_empty_page(self):
        glue_object = build_glue(Gorilla.objects.none(), page_size=3)

        result = glue_object.query_with_params()

        self.assertEqual(result['items'], [])
        self.assertEqual(result['total'], 0)
        self.assertEqual(result['page_count'], 1)

    def test_invalid_page_raises_validation_error(self):
        glue_object = build_glue(page_size=3)

        for page in (0, -2, True, 'two', 1.5, None):
            with self.assertRaises(GlueQuerySetPageValidationError) as context:
                glue_object.query_with_params(page=page)

            self.assertEqual(context.exception.status, 422)
            self.assertEqual(context.exception.details(), {'page': page})

    def test_filter_and_order_apply_before_pagination(self):
        glue_object = build_glue(page_size=2)

        result = glue_object.query_with_params(filter={'name__icontains': '0'}, order_by='-name', page=2)

        self.assertEqual(self._names(result), ['Gorilla 04', 'Gorilla 03'])
        self.assertEqual(result['total'], 7)
        self.assertEqual(result['page_count'], 4)

    def test_slice_narrows_the_queryset_before_pagination(self):
        glue_object = build_glue(page_size=2)

        result = glue_object.query_with_params(slice={'start': 1, 'stop': 4}, page=2)

        self.assertEqual(self._names(result), ['Gorilla 03'])
        self.assertEqual(result['total'], 3)
        self.assertEqual(result['page_count'], 2)

    def test_unordered_queryset_is_ordered_by_pk_for_stable_pages(self):
        glue_object = build_glue(Gorilla.objects.all(), page_size=3)

        with self.assertNumQueries(2) as captured:
            glue_object.query_with_params(page=2)

        self.assertIn('ORDER BY', captured.captured_queries[1]['sql'])
        self.assertIn('LIMIT 3 OFFSET 3', captured.captured_queries[1]['sql'])

    def test_explicit_ordering_is_preserved(self):
        glue_object = build_glue(page_size=3)

        result = glue_object.query_with_params(order_by='-name')

        self.assertEqual(self._names(result), ['Gorilla 06', 'Gorilla 05', 'Gorilla 04'])

    def test_unpaginated_query_does_not_count(self):
        glue_object = build_glue(page_size=None)

        with self.assertNumQueries(1):
            glue_object.query_with_params()

    def test_eager_state_is_the_first_page(self):
        glue_object = build_glue(page_size=3, loading_strategy=LoadingStrategy.EAGER)

        state = glue_object.state

        self.assertEqual(self._names(state), ['Gorilla 00', 'Gorilla 01', 'Gorilla 02'])
        self.assertEqual(state['total'], 7)
        self.assertEqual(state['page_count'], 3)

    def test_page_size_is_signed_into_the_policy_and_restored(self):
        glue_object = build_glue(page_size=2)

        self.assertEqual(glue_object.policy.identity['page_size'], 2)

        restored = QuerySetGlue._reconstruct_from_policy(GluePolicy.from_token(glue_object.policy.token))
        restored.request = request_with_session()
        restored.policy
        result = restored.query_with_params(page=4)

        self.assertEqual(restored.page_size, 2)
        self.assertEqual(self._names(result), ['Gorilla 06'])

    def test_unpaginated_policy_restores_as_unpaginated(self):
        glue_object = build_glue(page_size=None)

        restored = QuerySetGlue._reconstruct_from_policy(GluePolicy.from_token(glue_object.policy.token))

        self.assertIsNone(restored.page_size)


class RelatedSetPaginationTestCase(TestCase):
    def setUp(self):
        self.gorilla = Gorilla.objects.create(name='Koko', age=18)
        rival = Gorilla.objects.create(name='Rival', age=19)

        for index in range(5):
            Fight.objects.create(name=f'Fight {index}', red_corner=self.gorilla, blue_corner=rival)

    @override_settings(DJANGO_GLUE_QUERYSET_PAGE_SIZE=2)
    def test_prefetched_related_set_state_is_paginated_in_memory(self):
        instance = Gorilla.objects.prefetch_related('fights_as_red_corner').get(pk=self.gorilla.pk)
        glue_object = ModelGlue(
            instance,
            name='gorilla',
            access=GlueAccess.VIEW,
            fields=['name', 'fights_as_red_corner'],
        )
        glue_object.request = request_with_session()
        glue_object.policy
        attribute = glue_object.attributes['fights_as_red_corner']

        self.assertIsInstance(attribute, RelatedSetFieldAttribute)

        with self.assertNumQueries(0):
            state = attribute.state

        self.assertEqual(len(state['items']), 2)
        self.assertEqual(state['total'], 5)
        self.assertEqual(state['page_size'], 2)
        self.assertEqual(state['page_count'], 3)
