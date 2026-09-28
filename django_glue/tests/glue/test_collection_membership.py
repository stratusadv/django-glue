from __future__ import annotations

from django.test import TestCase

from django_glue.access import GlueAccess
from django_glue.exceptions import GlueRequestError
from django_glue.glue.objects.django.queryset import QuerySetGlue
from django_glue.glue.policy import GluePolicy
from django_glue.glue.sequence import SequenceGlue
from django_glue.tests.glue.test_objects import (
    DeclaredStateGlue,
    NestedStatsGlue,
    request_with_session,
    with_request,
)
from django_glue.tests.glue.test_refresh import request_entry
from test_project.gorilla.models import Gorilla


class QuerySetMembershipTestCase(TestCase):
    def setUp(self):
        self.gorillas = [Gorilla.objects.create(name=f'Gorilla {index:02d}') for index in range(7)]
        self.request = request_with_session()
        glue_object = QuerySetGlue(
            Gorilla.objects.all(),
            name='gorillas',
            access=GlueAccess.VIEW,
            fields=['name'],
            batch_size=3,
        )
        glue_object.request = self.request
        _entry, _introduced, self.policy = request_entry(
            QuerySetGlue, glue_object.policy, self.request, attribute='query_with_params',
        )

    def test_non_query_call_keeps_the_loaded_rows(self):
        _entry, introduced, successor = request_entry(
            QuerySetGlue, self.policy, self.request, attribute='count',
        )

        self.assertEqual(successor.children, self.policy.children)
        self.assertEqual(introduced, [])

    def test_continuing_the_cursor_keeps_the_earlier_rows(self):
        first, _introduced, _policy = request_entry(
            QuerySetGlue, self.policy, self.request, attribute='query_with_params',
        )

        _entry, _introduced, successor = request_entry(
            QuerySetGlue,
            self.policy,
            self.request,
            attribute='query_with_params',
            kwargs={'seek_key': first['result']['seek_key']},
        )

        self.assertEqual(len(successor.children), 6)
        for path, row_address in self.policy.children.items():
            self.assertEqual(successor.children[path], row_address)

    def test_restarting_the_query_replaces_the_window(self):
        _entry, _introduced, successor = request_entry(
            QuerySetGlue,
            self.policy,
            self.request,
            attribute='query_with_params',
            kwargs={'order_by': ['-name']},
        )

        self.assertEqual(len(successor.children), 3)
        self.assertEqual(
            set(successor.children),
            {str(gorilla.pk) for gorilla in self.gorillas[4:]},
        )

    def test_reintroducing_a_live_row_re_fetches_it_at_its_address(self):
        key, row_address = next(iter(self.policy.children.items()))
        Gorilla.objects.filter(pk=key).update(name='Renamed')

        _entry, introduced, successor = request_entry(
            QuerySetGlue, self.policy, self.request, attribute='count', reintroduce=[key],
        )

        self.assertEqual(successor.children, self.policy.children)
        self.assertEqual([entry['address'] for entry in introduced], [row_address])
        self.assertEqual(introduced[0]['computed_data']['name'], 'Renamed')

    def test_reintroducing_a_deleted_row_drops_it(self):
        key = next(iter(self.policy.children))
        Gorilla.objects.filter(pk=key).delete()

        _entry, _introduced, successor = request_entry(
            QuerySetGlue, self.policy, self.request, attribute='count', reintroduce=[key],
        )

        self.assertNotIn(key, successor.children)
        self.assertEqual(len(successor.children), 2)


class QuerySetRelationChildMembershipTestCase(TestCase):
    """The collection owns its projected relation children (state-model.md §4),
    so they follow the collection's slot rules (§10): live ones carry forward,
    and an expired one is reintroduced through the collection at its existing
    address."""

    def setUp(self):
        from django_glue import Glue
        from test_project.fight.models import Fight

        self.koko = Gorilla.objects.create(name='Koko', age=18)
        self.rival = Gorilla.objects.create(name='Rival', age=19)
        self.fights = [
            Fight.objects.create(name=f'Fight {index}', red_corner=self.koko, blue_corner=self.rival)
            for index in range(2)
        ]
        self.request = request_with_session()
        glue_object = QuerySetGlue(
            Fight.objects.all(),
            name='fights',
            access=GlueAccess.VIEW,
            fields=Glue.fields('id', 'name', red_corner=('name',)),
        )
        glue_object.request = self.request
        _entry, _introduced, self.policy = request_entry(
            QuerySetGlue, glue_object.policy, self.request, attribute='query_with_params',
        )
        self.path = f'red_corner.{self.koko.pk}'

    def test_a_non_query_call_carries_the_relation_child_forward(self):
        _entry, introduced, successor = request_entry(
            QuerySetGlue, self.policy, self.request, attribute='count',
        )

        self.assertEqual(successor.children[self.path], self.policy.children[self.path])
        self.assertEqual(introduced, [])

    def test_reintroducing_a_live_relation_child_rebuilds_it_at_its_address(self):
        Gorilla.objects.filter(pk=self.koko.pk).update(name='Koko Renamed')

        _entry, introduced, successor = request_entry(
            QuerySetGlue,
            self.policy,
            self.request,
            attribute='count',
            reintroduce=[self.path],
        )

        address = self.policy.children[self.path]
        self.assertEqual(successor.children[self.path], address)
        self.assertEqual([entry['address'] for entry in introduced], [address])
        self.assertEqual(introduced[0]['computed_data']['name'], 'Koko Renamed')

    def test_reintroducing_a_relation_child_no_row_references_drops_it(self):
        from test_project.fight.models import Fight

        Fight.objects.update(red_corner=self.rival)

        _entry, introduced, successor = request_entry(
            QuerySetGlue,
            self.policy,
            self.request,
            attribute='count',
            reintroduce=[self.path],
        )

        self.assertNotIn(self.path, successor.children)
        self.assertEqual(introduced, [])

    def test_reintroducing_a_relation_path_the_collection_never_issued_fails_admission(self):
        with self.assertRaises(GlueRequestError):
            request_entry(
                QuerySetGlue,
                self.policy,
                self.request,
                attribute='count',
                reintroduce=[f'red_corner.{self.rival.pk}'],
            )


class SequenceMembershipTestCase(TestCase):
    def setUp(self):
        self.request = request_with_session()
        glue_object = with_request(SequenceGlue(
            [NestedStatsGlue(), DeclaredStateGlue()],
            name='dashboard_items',
            access=GlueAccess.VIEW,
        ))
        self.request = glue_object.request
        self.policy = glue_object.policy

    def test_refresh_carries_live_items_forward(self):
        _entry, introduced, successor = request_entry(SequenceGlue, self.policy, self.request)

        self.assertEqual(successor.children, self.policy.children)
        self.assertEqual(introduced, [])

    def test_reintroducing_a_sequence_item_fails_admission(self):
        with self.assertRaises(GlueRequestError):
            request_entry(SequenceGlue, self.policy, self.request, reintroduce=['stats'])

    def test_an_item_refused_introduction_is_left_out(self):
        glue_object = with_request(SequenceGlue(
            [NestedStatsGlue(), RefusedStateGlue()],
            name='dashboard_items',
            access=GlueAccess.VIEW,
        ))

        item_policies = [
            GluePolicy.from_token(entry['policy_token'])
            for entry in glue_object._serialized_child_entries()
        ]

        self.assertEqual(list(glue_object.policy.children), ['stats'])
        self.assertEqual([policy.namespace for policy in item_policies], ['stats'])


class RefusedStateGlue(DeclaredStateGlue):
    def is_authorized(self, request, operation):
        _ = request, operation
        return False
