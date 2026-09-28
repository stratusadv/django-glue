from __future__ import annotations

import base64
import json

from datetime import UTC, datetime
from types import SimpleNamespace

from django.db.models.functions import Length
from django.test import TestCase, override_settings

from django_glue import Glue
from django_glue.access import GlueAccess
from django_glue.exceptions import (
    GlueQuerySetCursorValidationError,
    GlueQuerySetFilterValidationError,
    GlueQuerySetOrderValidationError,
    GlueQuerySetSliceValidationError,
)
from django_glue.glue.objects.django.queryset import QuerySetGlue
from django_glue.glue.policy import GluePolicy
from django_glue.glue.objects.django.model.object import ModelGlue
from django_glue.tests.glue.addressed_rows import addressed_row_entries
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

    def _names(self, glue_object, result):
        return [row['computed_data']['name'] for row in addressed_row_entries(glue_object, result)]

    def _all_names_via_cursor(self, glue_object, **params):
        names = []
        seek_key = None
        for _ in range(20):  # generous upper bound so a broken loop fails fast, not forever
            result = glue_object.query_with_params(seek_key=seek_key, **params)
            names.extend(self._names(glue_object, result))
            if not result['has_next']:
                return names
            seek_key = result['seek_key']
        raise AssertionError('cursor never terminated')

    def test_choice_queryset_config_propagates_to_child_model_policy(self):
        visible = Skill.objects.create(name='Visible')
        Skill.objects.create(name='Hidden')
        glue_object = build_glue(
            fields=['id', 'name', 'skills'],
            choices={
                'skills': Glue.choices(
                    Skill.objects.filter(name='Visible'),
                    fields=['name'],
                ),
            },
        )

        restored_queryset = QuerySetGlue._reconstruct_from_policy(glue_object.policy)
        restored_queryset.request = request_with_session()
        child = restored_queryset._row_glue(restored_queryset.queryset.first())
        child_policy = child.policy
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

        self.assertEqual(self._names(glue_object, result), ['Gorilla 00', 'Gorilla 01', 'Gorilla 02'])
        self.assertTrue(result['has_next'])
        self.assertIsNotNone(result['seek_key'])
        self.assertEqual(result['batch_size'], 3)

    def test_cursor_memory_is_signed_as_retained_state_not_identity(self):
        from django_glue.tests.glue.test_callable_parameters import call_context

        glue_object = build_glue(batch_size=3)
        context = call_context(glue_object, 'query_with_params', kwargs={'order_by': ['name']})
        reconstructed = QuerySetGlue.from_attribute_call_resolver_context(context)

        entry, _introduced = reconstructed.process_attribute_call(context)
        successor = GluePolicy.from_token(entry['policy_token'])

        self.assertNotIn('loaded_row_count', successor.identity)
        self.assertNotIn('last_query_params', successor.identity)
        self.assertEqual(successor.state_snapshot['loaded_row_count'], 3)
        self.assertEqual(
            QuerySetGlue._reconstruct_from_policy(successor)._loaded_row_count,
            3,
        )

    def test_following_the_cursor_reaches_the_partial_last_page(self):
        glue_object = build_glue(batch_size=3)

        first = glue_object.query_with_params()
        second = glue_object.query_with_params(seek_key=first['seek_key'])
        third = glue_object.query_with_params(seek_key=second['seek_key'])

        self.assertEqual(self._names(glue_object, second), ['Gorilla 03', 'Gorilla 04', 'Gorilla 05'])
        self.assertTrue(second['has_next'])
        self.assertEqual(self._names(glue_object, third), ['Gorilla 06'])
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

    def test_unsigned_or_forged_seek_position_is_rejected(self):
        glue_object = build_glue(batch_size=3)
        issued = glue_object.query_with_params()['seek_key']
        position, signature = issued.rsplit(':', 1)
        forged_position = base64.urlsafe_b64encode(
            json.dumps(['Gorilla 05', Gorilla.objects.get(name='Gorilla 05').pk]).encode(),
        ).decode()

        for seek_key in (position, forged_position, f'{forged_position}:{signature}'):
            with self.assertRaises(GlueQuerySetCursorValidationError):
                glue_object.query_with_params(seek_key=seek_key)

    def test_seek_key_is_rejected_under_a_different_query(self):
        glue_object = build_glue(batch_size=3)
        issued = glue_object.query_with_params(order_by=['name'])['seek_key']

        with self.assertRaises(GlueQuerySetCursorValidationError):
            glue_object.query_with_params(order_by=['-name'], seek_key=issued)

        with self.assertRaises(GlueQuerySetCursorValidationError):
            glue_object.query_with_params(
                filter={'name__icontains': 'Gorilla'},
                order_by=['name'],
                seek_key=issued,
            )

    def test_seek_key_is_rejected_by_another_queryset(self):
        issued = build_glue(batch_size=3).query_with_params()['seek_key']
        other = QuerySetGlue(
            Gorilla.objects.all(),
            name='other_gorillas',
            access=GlueAccess.VIEW,
            fields=['id', 'name'],
            batch_size=3,
        )
        other.request = request_with_session()
        other.policy

        with self.assertRaises(GlueQuerySetCursorValidationError):
            other.query_with_params(seek_key=issued)

    def test_refreshed_window_issues_a_seek_key_the_next_batch_accepts(self):
        glue_object = build_glue(batch_size=3)
        glue_object.query_with_params(order_by=['name'])

        refreshed = glue_object._loaded_window()
        following = glue_object.query_with_params(order_by=['name'], seek_key=refreshed['seek_key'])

        self.assertEqual(
            self._names(glue_object, following),
            ['Gorilla 03', 'Gorilla 04', 'Gorilla 05'],
        )

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
        self.assertEqual(self._names(glue_object, first), ['Gorilla 00', 'Gorilla 01'])
        self.assertTrue(first['has_next'])

        second = glue_object.query_with_params(slice={'start': 0, 'stop': 4}, seek_key=first['seek_key'])
        self.assertEqual(self._names(glue_object, second), ['Gorilla 02', 'Gorilla 03'])

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

        self.assertEqual(self._names(glue_object, result), ['Gorilla 06', 'Gorilla 05', 'Gorilla 04'])

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

    def test_introduction_carries_no_rows(self):
        glue_object = build_glue(batch_size=3)

        entry = glue_object.entry

        self.assertNotIn('items', entry.computed_data)
        self.assertEqual(glue_object._serialized_child_entries(), [])

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

    def test_filter_rejects_unapproved_lookup_on_exposed_field(self):
        glue_object = build_glue()

        with self.assertRaises(GlueQuerySetFilterValidationError):
            glue_object.query_with_params(filter={'name__regex': 'Gorilla'})

    def test_order_rejects_hidden_field(self):
        glue_object = build_glue()

        with self.assertRaises(GlueQuerySetOrderValidationError):
            glue_object.query_with_params(order_by='age')

    def test_order_rejects_expression(self):
        glue_object = build_glue()

        with self.assertRaises(GlueQuerySetOrderValidationError):
            glue_object.query_with_params(order_by='?')

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

    def _names(self, glue_object, result):
        return [row['computed_data']['name'] for row in addressed_row_entries(glue_object, result)]

    def _all_names_via_cursor(self, glue_object, **params):
        names = []
        seek_key = None
        for _ in range(20):
            result = glue_object.query_with_params(seek_key=seek_key, **params)
            names.extend(self._names(glue_object, result))
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

    def test_continuation_follows_a_related_ordering_path(self):
        for index, name in enumerate(['Delta', 'Alpha', 'Echo', 'Charlie', 'Bravo']):
            Fight.objects.create(
                name=f'Ranked {index}',
                red_corner=Gorilla.objects.create(name=name, age=index),
                blue_corner=Gorilla.objects.get(name='Rival'),
            )
        glue_object = QuerySetGlue(
            Fight.objects.filter(name__startswith='Ranked'),
            name='fights',
            access=GlueAccess.VIEW,
            fields=['id', 'name'],
            ordering=['red_corner__name', 'winner__name'],
            batch_size=2,
        )
        glue_object.request = request_with_session()
        glue_object.policy

        by_red_corner = self._all_names_via_cursor(glue_object, order_by='-red_corner__name')
        by_nullable_winner = self._all_names_via_cursor(glue_object, order_by='winner__name')

        self.assertEqual(
            by_red_corner,
            ['Ranked 2', 'Ranked 0', 'Ranked 3', 'Ranked 4', 'Ranked 1'],
        )
        self.assertEqual(sorted(by_nullable_winner), [f'Ranked {index}' for index in range(5)])

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
            [row['computed_data']['status'] for row in addressed_row_entries(glue_object, ascending)][-3:],
            [None, None, None],
        )
        self.assertEqual(
            [row['computed_data']['status'] for row in addressed_row_entries(glue_object, descending)][-3:],
            [None, None, None],
        )


class RelatedSetPaginationTestCase(TestCase):
    def setUp(self):
        self.gorilla = Gorilla.objects.create(name='Koko', age=18)
        rival = Gorilla.objects.create(name='Rival', age=19)

        for index in range(5):
            Fight.objects.create(name=f'Fight {index}', red_corner=self.gorilla, blue_corner=rival)

    @override_settings(DJANGO_GLUE_QUERYSET_BATCH_SIZE=2)
    def test_projected_related_collection_uses_queryset_pagination(self):
        glue_object = ModelGlue(
            self.gorilla,
            name='gorilla',
            access=GlueAccess.VIEW,
            fields=[
                'name',
                'fights_as_red_corner__id',
                'fights_as_red_corner__name',
            ],
        )
        glue_object.request = request_with_session()
        child = glue_object._bound_children[0].glue_object

        self.assertIsInstance(child, QuerySetGlue)
        state = child.state

        self.assertEqual(len(state['items']), 2)
        self.assertTrue(state['has_next'])
        self.assertEqual(state['batch_size'], 2)


class ProjectedQueryCapabilityTestCase(TestCase):
    def setUp(self):
        self.alpha = Gorilla.objects.create(name='Alpha', age=12)
        self.beta = Gorilla.objects.create(name='Beta', age=24)
        Fight.objects.create(name='First Bout', red_corner=self.alpha, blue_corner=self.beta)
        Fight.objects.create(name='Second Bout', red_corner=self.beta, blue_corner=self.alpha)

    def test_projected_relation_filter_and_order_survive_signed_reconstruction(self):
        glue_object = QuerySetGlue(
            Fight.objects.all(),
            name='fights',
            fields=Glue.fields('id', 'name', red_corner=('name',)),
            batch_size=None,
        )
        glue_object.request = request_with_session()
        policy = GluePolicy.from_token(glue_object.policy.token)
        restored = QuerySetGlue._reconstruct_from_policy(policy)
        restored.request = request_with_session()

        self.assertIn('icontains', policy.capability.query.filters['red_corner__name'])
        self.assertIn('red_corner__name', policy.capability.query.ordering)
        result = restored.query_with_params(
            filter={'red_corner__name__icontains': 'alp'},
            order_by='red_corner__name',
        )

        self.assertEqual(
            [row['computed_data']['name'] for row in addressed_row_entries(restored, result)],
            ['First Bout'],
        )

    def test_projected_relation_does_not_expose_other_related_fields(self):
        glue_object = QuerySetGlue(
            Fight.objects.all(),
            name='fights',
            fields=Glue.fields('id', 'name', red_corner=('name',)),
        )
        glue_object.request = request_with_session()

        with self.assertRaises(GlueQuerySetFilterValidationError):
            glue_object.query_with_params(filter={'red_corner__age__gte': 18})
        with self.assertRaises(GlueQuerySetOrderValidationError):
            glue_object.query_with_params(order_by='red_corner__age')

    def test_projected_relation_keeps_raw_identity_queries(self):
        glue_object = QuerySetGlue(
            Fight.objects.all(),
            name='fights',
            fields=Glue.fields('id', 'name', red_corner=('name',)),
            batch_size=None,
        )
        glue_object.request = request_with_session()

        result = glue_object.query_with_params(
            filter={'red_corner': self.alpha.pk},
            order_by='red_corner',
        )
        self.assertEqual(len(result['items']), 1)

    def test_invalid_explicit_query_paths_are_rejected_at_introduction(self):
        with self.assertRaises(ValueError):
            QuerySetGlue(
                Fight.objects.all(),
                fields=['id'],
                filters={'red_corner__password': ['exact']},
            )
        with self.assertRaises(ValueError):
            QuerySetGlue(
                Fight.objects.all(),
                fields=['id'],
                ordering=['red_corner__password'],
            )

    def test_explicit_hidden_path_is_limited_to_declared_lookup_and_order(self):
        glue_object = QuerySetGlue(
            Fight.objects.all(),
            name='fights',
            fields=['id', 'name'],
            filters={'red_corner__age': ['gte']},
            ordering=['name'],
            batch_size=None,
        )
        glue_object.request = request_with_session()

        result = glue_object.query_with_params(filter={'red_corner__age__gte': 18})
        self.assertEqual(len(result['items']), 1)
        with self.assertRaises(GlueQuerySetFilterValidationError):
            glue_object.query_with_params(filter={'red_corner__age__lte': 18})
        with self.assertRaises(GlueQuerySetOrderValidationError):
            glue_object.query_with_params(order_by='red_corner__age')

    def test_explicit_reverse_traversal_is_signed_and_limited(self):
        glue_object = QuerySetGlue(
            Gorilla.objects.all(),
            name='gorillas',
            fields=['id', 'name'],
            filters={'fights_as_red_corner__name': ['icontains']},
            ordering=['fights_as_red_corner__name'],
            batch_size=None,
        )
        glue_object.request = request_with_session()
        restored = QuerySetGlue._reconstruct_from_policy(
            GluePolicy.from_token(glue_object.policy.token)
        )
        restored.request = request_with_session()

        result = restored.query_with_params(
            filter={'fights_as_red_corner__name__icontains': 'First'},
            order_by='fights_as_red_corner__name',
        )
        self.assertEqual(len(result['items']), 1)
        with self.assertRaises(GlueQuerySetFilterValidationError):
            restored.query_with_params(filter={'fights_as_red_corner__name__regex': 'First'})

    def test_explicit_annotation_is_signed_and_limited(self):
        glue_object = QuerySetGlue(
            Gorilla.objects.annotate(name_length=Length('name')),
            name='gorillas',
            fields=['id', 'name'],
            filters={'name_length': ['gte']},
            ordering=['name_length'],
            batch_size=None,
        )
        glue_object.request = request_with_session()
        restored = QuerySetGlue._reconstruct_from_policy(
            GluePolicy.from_token(glue_object.policy.token)
        )
        restored.request = request_with_session()

        result = restored.query_with_params(
            filter={'name_length__gte': 5}, order_by='name_length'
        )
        self.assertEqual(len(result['items']), 1)
        with self.assertRaises(GlueQuerySetFilterValidationError):
            restored.query_with_params(filter={'name_length__lt': 5})

    def test_explicit_transform_is_signed_and_limited(self):
        Fight.objects.filter(name='First Bout').update(
            date_time=datetime(2024, 2, 3, tzinfo=UTC)
        )
        Fight.objects.filter(name='Second Bout').update(
            date_time=datetime(2026, 2, 3, tzinfo=UTC)
        )
        glue_object = QuerySetGlue(
            Fight.objects.all(),
            name='fights',
            fields=['id', 'name', 'date_time'],
            filters={'date_time__year': ['gte']},
            ordering=['date_time__year'],
            batch_size=None,
        )
        glue_object.request = request_with_session()
        restored = QuerySetGlue._reconstruct_from_policy(
            GluePolicy.from_token(glue_object.policy.token)
        )
        restored.request = request_with_session()

        result = restored.query_with_params(
            filter={'date_time__year__gte': 2025}, order_by='date_time__year'
        )
        self.assertEqual(len(result['items']), 1)
        with self.assertRaises(GlueQuerySetFilterValidationError):
            restored.query_with_params(filter={'date_time__year__lt': 2025})

    def test_advanced_paths_are_not_derived_by_default(self):
        glue_object = QuerySetGlue(
            Gorilla.objects.annotate(name_length=Length('name')),
            name='gorillas',
            fields=['id', 'name'],
        )
        glue_object.request = request_with_session()

        for key in (
            'name_length__gte',
            'name__lower__exact',
            'fights_as_red_corner__name__icontains',
        ):
            with self.assertRaises(GlueQuerySetFilterValidationError):
                glue_object.query_with_params(filter={key: 'Alpha'})
        with self.assertRaises(GlueQuerySetOrderValidationError):
            glue_object.query_with_params(order_by='name_length')

    def test_registered_unusual_lookup_requires_explicit_declaration(self):
        glue_object = QuerySetGlue(
            Gorilla.objects.all(),
            name='gorillas',
            fields=['id', 'name'],
            filters={'name': ['regex']},
            batch_size=None,
        )
        glue_object.request = request_with_session()

        result = glue_object.query_with_params(filter={'name__regex': '^Al'})
        self.assertEqual(len(result['items']), 1)
        with self.assertRaises(GlueQuerySetFilterValidationError):
            glue_object.query_with_params(filter={'name__icontains': 'Al'})
