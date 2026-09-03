from __future__ import annotations

from types import SimpleNamespace

from django.test import TestCase, override_settings

from django_glue import ALL_FIELDS, Glue
from django_glue.access import GlueAccess
from django_glue.exceptions import (
    GlueQuerySetCursorValidationError,
    GlueQuerySetFilterValidationError,
    GlueQuerySetSliceValidationError,
)
from django_glue.glue.objects.django.queryset import QuerySetGlue
from django_glue.glue.policy import GluePolicy
from django_glue.glue.loading import LoadingStrategy
from django_glue.glue.attributes.django.model.related_set import RelatedSetFieldAttribute
from django_glue.glue.objects.django.model.object import ModelGlue
from test_project.fight.models import Fight
from test_project.gorilla.models import Gorilla, Skill


def request_with_session(session_key='test-session'):
    return SimpleNamespace(session=SimpleNamespace(session_key=session_key), FILES={})


def build_glue(queryset=None, **kwargs):
    kwargs.setdefault('fields', ['id', 'name'])
    glue_object = QuerySetGlue(
        Gorilla.objects.all() if queryset is None else queryset,
        name='gorillas',
        access=GlueAccess.VIEW,
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

    def _all_names_via_cursor(self, glue_object, **params):
        names = []
        seek_key = None
        for _ in range(20):  # generous upper bound so a broken loop fails fast, not forever
            result = glue_object.query_with_params(seek_key=seek_key, **params)
            names.extend(self._names(result))
            if not result['has_next']:
                return names
            seek_key = result['seek_key']
        raise AssertionError('cursor never terminated')

    def test_choice_queryset_config_propagates_to_child_model_policy(self):
        visible = Skill.objects.create(name='Visible')
        Skill.objects.create(name='Hidden')
        glue_object = build_glue(
            fields=['id', 'name', 'skills'],
            related_field_config={
                'skills': {
                    'choice_queryset': Glue.choices(
                        Skill.objects.filter(name='Visible'),
                        fields=['name'],
                    ),
                },
            },
        )

        restored_queryset = QuerySetGlue._reconstruct_from_policy(glue_object.policy)
        restored_queryset.request = request_with_session()
        child_payload = restored_queryset._build_child_model_payload(
            restored_queryset.queryset.first()
        )
        child_policy = GluePolicy.from_token(child_payload['policy_token'])
        child = ModelGlue._reconstruct_from_policy(child_policy)

        result = child.foreign_key_choices(field_name='skills')

        self.assertEqual(
            [choice['value'] for choice in result['results']],
            [visible.pk],
        )
        self.assertEqual(result['results'][0]['obj']['name'], 'Visible')

    def test_batch_size_defaults_to_setting(self):
        with override_settings(DJANGO_GLUE_QUERYSET_BATCH_SIZE=3):
            glue_object = build_glue()

        self.assertEqual(glue_object.batch_size, 3)

    def test_batch_size_none_disables_pagination(self):
        glue_object = build_glue(batch_size=None)

        result = glue_object.query_with_params()

        self.assertEqual(len(result['items']), 7)
        self.assertIsNone(result['seek_key'])
        self.assertFalse(result['has_next'])
        self.assertIsNone(result['batch_size'])

    def test_invalid_batch_size_raises(self):
        for batch_size in (0, -1, True, '5', 2.5):
            with self.assertRaises(ValueError):
                build_glue(batch_size=batch_size)

    def test_first_page_is_bounded_and_has_next(self):
        glue_object = build_glue(batch_size=3)

        result = glue_object.query_with_params()

        self.assertEqual(self._names(result), ['Gorilla 00', 'Gorilla 01', 'Gorilla 02'])
        self.assertTrue(result['has_next'])
        self.assertIsNotNone(result['seek_key'])
        self.assertEqual(result['batch_size'], 3)

    def test_following_the_cursor_reaches_the_partial_last_page(self):
        glue_object = build_glue(batch_size=3)

        first = glue_object.query_with_params()
        second = glue_object.query_with_params(seek_key=first['seek_key'])
        third = glue_object.query_with_params(seek_key=second['seek_key'])

        self.assertEqual(self._names(second), ['Gorilla 03', 'Gorilla 04', 'Gorilla 05'])
        self.assertTrue(second['has_next'])
        self.assertEqual(self._names(third), ['Gorilla 06'])
        self.assertFalse(third['has_next'])
        self.assertIsNone(third['seek_key'])

    def test_full_scan_via_cursor_visits_every_row_once(self):
        glue_object = build_glue(batch_size=3)

        names = self._all_names_via_cursor(glue_object)

        self.assertEqual(names, [f'Gorilla {index:02d}' for index in range(7)])

    def test_invalid_seek_key_raises_validation_error(self):
        glue_object = build_glue(batch_size=3)

        for seek_key in ('not-base64!!', 'AAAA', ''):
            with self.assertRaises(GlueQuerySetCursorValidationError) as context:
                glue_object.query_with_params(seek_key=seek_key)

            self.assertEqual(context.exception.status, 422)
            self.assertEqual(context.exception.details(), {'seek_key': seek_key})

    def test_empty_queryset_has_no_next(self):
        glue_object = build_glue(Gorilla.objects.none(), batch_size=3)

        result = glue_object.query_with_params()

        self.assertEqual(result['items'], [])
        self.assertFalse(result['has_next'])
        self.assertIsNone(result['seek_key'])

    def test_filter_and_order_apply_before_pagination(self):
        glue_object = build_glue(batch_size=2)

        names = self._all_names_via_cursor(glue_object, filter={'name__icontains': '0'}, order_by='-name')

        self.assertEqual(names, [f'Gorilla {index:02d}' for index in range(6, -1, -1)])

    def test_slice_narrows_the_queryset_before_pagination(self):
        glue_object = build_glue(batch_size=5)

        names = self._all_names_via_cursor(glue_object, slice={'start': 1, 'stop': 4})

        self.assertEqual(names, ['Gorilla 01', 'Gorilla 02', 'Gorilla 03'])

    def test_slice_missing_stop_is_rejected_instead_of_silently_unbounded(self):
        # `slice.get('stop') or 0` used to make an omitted `stop` compute a
        # non-positive width, which skipped the check entirely and let an
        # open-ended slice through with no bound at all.
        glue_object = build_glue(batch_size=5)

        with self.assertRaises(GlueQuerySetSliceValidationError) as context:
            glue_object.query_with_params(slice={'start': 5})

        self.assertIsNone(context.exception.width)

    def test_slice_wider_than_batch_size_can_be_continued_with_seek_key(self):
        # A slice's width can exceed batch_size once loaded_row_count already
        # covers it (see the width-validation tests above). Continuing to
        # page through that wider slice via seek_key used to crash -- Django
        # can't `.filter()` a queryset that's already had a Python slice
        # applied, and `_seek_filter()` does exactly that on the second call.
        glue_object = build_glue(batch_size=2)
        self._all_names_via_cursor(glue_object)  # loaded_row_count now covers all 7 rows

        first = glue_object.query_with_params(slice={'start': 0, 'stop': 4})
        self.assertEqual(self._names(first), ['Gorilla 00', 'Gorilla 01'])
        self.assertTrue(first['has_next'])

        second = glue_object.query_with_params(slice={'start': 0, 'stop': 4}, seek_key=first['seek_key'])
        self.assertEqual(self._names(second), ['Gorilla 02', 'Gorilla 03'])

    def test_unordered_queryset_is_ordered_by_pk_and_seeks_without_offset(self):
        glue_object = build_glue(Gorilla.objects.all(), batch_size=3)
        first = glue_object.query_with_params()

        with self.assertNumQueries(1) as captured:
            glue_object.query_with_params(seek_key=first['seek_key'])

        sql = captured.captured_queries[0]['sql']
        self.assertIn('ORDER BY', sql)
        self.assertNotIn('OFFSET', sql)

    def test_explicit_ordering_is_preserved(self):
        glue_object = build_glue(batch_size=3)

        result = glue_object.query_with_params(order_by='-name')

        self.assertEqual(self._names(result), ['Gorilla 06', 'Gorilla 05', 'Gorilla 04'])

    def test_non_unique_ordering_field_still_produces_stable_pages(self):
        # Every gorilla shares the same weight, so pk is the only thing that
        # can make paging over `order_by='weight'` deterministic.
        glue_object = build_glue(batch_size=2, fields=['id', 'name', 'weight'])

        names = self._all_names_via_cursor(glue_object, order_by='weight')

        self.assertEqual(sorted(names), sorted(f'Gorilla {index:02d}' for index in range(7)))
        self.assertEqual(len(names), 7)  # every row exactly once -- no skip, no duplicate

    def test_non_unique_ordering_field_gets_pk_tiebreaker_in_the_real_sql(self):
        # The previous test (stable pages on SQLite) can pass "by accident"
        # since SQLite tends to return ties in rowid order anyway, even with
        # no explicit tiebreaker. Assert the tiebreaker is actually in the
        # generated SQL, not just that this backend happened to cooperate.
        glue_object = build_glue(batch_size=2, fields=['id', 'name', 'weight'])

        with self.assertNumQueries(1) as captured:
            glue_object.query_with_params(order_by='weight')

        order_by_clause = captured.captured_queries[0]['sql'].split('ORDER BY', 1)[1]
        self.assertIn('id', order_by_clause)

    def test_unpaginated_query_does_not_count(self):
        glue_object = build_glue(batch_size=None)

        with self.assertNumQueries(1):
            glue_object.query_with_params()

    def test_paginated_query_does_not_count(self):
        glue_object = build_glue(batch_size=3)

        with self.assertNumQueries(1):
            glue_object.query_with_params()

    def test_eager_state_is_the_first_page(self):
        glue_object = build_glue(batch_size=3, loading_strategy=LoadingStrategy.EAGER)

        state = glue_object.state

        self.assertEqual(self._names(state), ['Gorilla 00', 'Gorilla 01', 'Gorilla 02'])
        self.assertTrue(state['has_next'])

    def test_batch_size_is_signed_into_the_policy_and_restored(self):
        glue_object = build_glue(batch_size=2)

        self.assertEqual(glue_object.policy.identity['batch_size'], 2)

        restored = QuerySetGlue._reconstruct_from_policy(GluePolicy.from_token(glue_object.policy.token))
        restored.request = request_with_session()
        restored.policy

        self.assertEqual(restored.batch_size, 2)
        names = self._all_names_via_cursor(restored)
        self.assertEqual(names, [f'Gorilla {index:02d}' for index in range(7)])

    def test_unpaginated_policy_restores_as_unpaginated(self):
        glue_object = build_glue(batch_size=None)

        restored = QuerySetGlue._reconstruct_from_policy(GluePolicy.from_token(glue_object.policy.token))

        self.assertIsNone(restored.batch_size)


class QuerySetCountTestCase(TestCase):
    def setUp(self):
        for index in range(7):
            Gorilla.objects.create(name=f'Gorilla {index:02d}', age=index, weight=100.0, height=1.5)

    def test_count_returns_total_matching_rows(self):
        glue_object = build_glue(batch_size=3)

        self.assertEqual(glue_object.count(), 7)

    def test_count_respects_filter(self):
        glue_object = build_glue(batch_size=3)

        self.assertEqual(glue_object.count(filter={'name__icontains': 'Gorilla 0'}), 7)
        self.assertEqual(glue_object.count(filter={'name': 'Gorilla 03'}), 1)
        self.assertEqual(glue_object.count(filter={'name': 'no such gorilla'}), 0)

    def test_count_validates_filter_fields(self):
        glue_object = build_glue(batch_size=3)

        with self.assertRaises(GlueQuerySetFilterValidationError):
            glue_object.count(filter={'age__gt': 1})

    def test_count_is_independent_of_seek_batch(self):
        glue_object = build_glue(batch_size=3)

        with self.assertNumQueries(1):
            glue_object.query_with_params()

        with self.assertNumQueries(1):
            glue_object.count()


class QuerySetWithTotalTestCase(TestCase):
    def setUp(self):
        for index in range(7):
            Gorilla.objects.create(name=f'Gorilla {index:02d}', age=index, weight=100.0, height=1.5)

    def test_with_total_false_omits_total(self):
        glue_object = build_glue(batch_size=3)

        result = glue_object.query_with_params()

        self.assertNotIn('total', result)

    def test_with_total_true_includes_total_matching_filter(self):
        glue_object = build_glue(batch_size=3)

        result = glue_object.query_with_params(with_total=True)
        self.assertEqual(result['total'], 7)

        result = glue_object.query_with_params(filter={'name': 'Gorilla 03'}, with_total=True)
        self.assertEqual(result['total'], 1)

    def test_with_total_costs_exactly_one_extra_query(self):
        glue_object = build_glue(batch_size=3)

        with self.assertNumQueries(1):
            glue_object.query_with_params()

        with self.assertNumQueries(2):
            glue_object.query_with_params(with_total=True)

    def test_with_total_is_independent_of_slice_and_seek_key(self):
        glue_object = build_glue(batch_size=3)

        first = glue_object.query_with_params(with_total=True)
        second = glue_object.query_with_params(seek_key=first['seek_key'], with_total=True)

        self.assertEqual(first['total'], 7)
        self.assertEqual(second['total'], 7)


class QuerySetNullOrderingTestCase(TestCase):
    """Seeking past a row whose order_by field is NULL (Fight.status is nullable)."""

    def setUp(self):
        gorilla = Gorilla.objects.create(name='Koko', age=18)
        rival = Gorilla.objects.create(name='Rival', age=19)
        # A mix of NULL and non-NULL statuses, deliberately not created in
        # sorted order, so a naive scan wouldn't happen to visit them in the
        # right order by coincidence.
        for index, status in enumerate([None, 'sch', None, 'cmp', None, 'inp']):
            Fight.objects.create(
                name=f'Fight {index}', red_corner=gorilla, blue_corner=rival, status=status,
            )

    def _names(self, result):
        return [row['state']['name']['value'] for row in result['items']]

    def _all_names_via_cursor(self, glue_object, **params):
        names = []
        seek_key = None
        for _ in range(20):
            result = glue_object.query_with_params(seek_key=seek_key, **params)
            names.extend(self._names(result))
            if not result['has_next']:
                return names
            seek_key = result['seek_key']
        raise AssertionError('cursor never terminated')

    def test_seeking_past_a_null_ordering_value_does_not_raise(self):
        glue_object = QuerySetGlue(
            Fight.objects.all(),
            name='fights',
            access=GlueAccess.VIEW,
            fields=['id', 'name', 'status'],
            batch_size=2,
        )
        glue_object.request = request_with_session()
        glue_object.policy

        names = self._all_names_via_cursor(glue_object, order_by='status')

        self.assertEqual(sorted(names), sorted(f'Fight {index}' for index in range(6)))
        self.assertEqual(len(names), 6)  # every row exactly once -- no skip, no duplicate

    def test_null_ordering_values_sort_last_regardless_of_direction(self):
        glue_object = QuerySetGlue(
            Fight.objects.all(),
            name='fights',
            access=GlueAccess.VIEW,
            fields=['id', 'name', 'status'],
            batch_size=None,
        )
        glue_object.request = request_with_session()
        glue_object.policy

        ascending = glue_object.query_with_params(order_by='status')
        descending = glue_object.query_with_params(order_by='-status')

        # Whichever direction, the three NULL-status fights land at the end.
        self.assertEqual(
            [row['state']['status']['value'] for row in ascending['items']][-3:],
            [None, None, None],
        )
        self.assertEqual(
            [row['state']['status']['value'] for row in descending['items']][-3:],
            [None, None, None],
        )


class RelatedSetPaginationTestCase(TestCase):
    def setUp(self):
        self.gorilla = Gorilla.objects.create(name='Koko', age=18)
        rival = Gorilla.objects.create(name='Rival', age=19)

        for index in range(5):
            Fight.objects.create(name=f'Fight {index}', red_corner=self.gorilla, blue_corner=rival)

    @override_settings(DJANGO_GLUE_QUERYSET_BATCH_SIZE=2)
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
        self.assertTrue(state['has_next'])
        self.assertEqual(state['batch_size'], 2)
