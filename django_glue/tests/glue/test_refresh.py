from __future__ import annotations

from typing import Any

from django.test import TestCase

from django_glue.access import GlueAccess
from django_glue.glue.objects.django.model.object import ModelGlue
from django_glue.glue.objects.django.queryset import QuerySetGlue
from django_glue.glue.operation import GlueOperationKind
from django_glue.glue.policy import GluePolicy
from django_glue.resolver.attribute_call.context import AttributeCallRequestContext
from django_glue.tests.glue.test_objects import request_with_session
from test_project.gorilla.models import Gorilla


def request_entry(
    glue_class: type,
    policy: GluePolicy,
    request: Any,
    *,
    attribute: str | None = None,
    kwargs: dict[str, Any] | None = None,
    updates: dict[str, Any] | None = None,
    reintroduce: list[str] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], GluePolicy]:
    context = AttributeCallRequestContext.model_construct(
        request=request,
        target_glue_policy=policy,
        target_glue_updates=updates or {},
        target_attribute_name=attribute,
        target_attribute_call_kwargs=kwargs or {},
        reintroduce=reintroduce or [],
    )
    glue_object = glue_class.from_attribute_call_resolver_context(context)
    entry, introduced = glue_object.process_attribute_call(context)
    successor = GluePolicy.from_token(entry['policy_token']) if 'policy_token' in entry else policy
    return entry, introduced, successor


class ModelRefreshTestCase(TestCase):
    def setUp(self):
        self.gorilla = Gorilla.objects.create(name='Koko', age=18)
        self.request = request_with_session()
        glue_object = ModelGlue(
            self.gorilla,
            name='gorilla',
            access=GlueAccess.CHANGE,
            fields=['name', 'age'],
        )
        glue_object.request = self.request
        self.policy = glue_object.policy

    def test_refresh_re_reads_persisted_data_without_a_result(self):
        Gorilla.objects.filter(pk=self.gorilla.pk).update(age=30)

        entry, introduced, successor = request_entry(ModelGlue, self.policy, self.request)

        self.assertIsNone(entry['result'])
        self.assertEqual(entry['effects'], {'messages': []})
        self.assertEqual(successor.state_snapshot['age'], 30)
        self.assertEqual(introduced, [])

    def test_unsubmitted_refresh_keeps_the_acknowledged_draft(self):
        _entry, _introduced, drafted = request_entry(
            ModelGlue, self.policy, self.request, updates={'name': 'Draft'},
        )

        _entry, _introduced, refreshed = request_entry(ModelGlue, drafted, self.request)

        self.assertEqual(refreshed.state_snapshot['name'], 'Draft')
        self.assertEqual(Gorilla.objects.get(pk=self.gorilla.pk).name, 'Koko')

    def test_submitted_refresh_admits_updates(self):
        _entry, _introduced, successor = request_entry(
            ModelGlue, self.policy, self.request, updates={'age': '21'},
        )

        self.assertEqual(successor.state_snapshot['age'], 21)

    def test_refresh_and_submitted_refresh_authorize_their_operation_kind(self):
        seen: list[GlueOperationKind] = []
        original = ModelGlue.authorize

        def recording_authorize(glue_object, request, operation):
            if operation.attribute is None:
                seen.append(operation.kind)
            return original(glue_object, request, operation)

        ModelGlue.authorize = recording_authorize
        try:
            request_entry(ModelGlue, self.policy, self.request)
            request_entry(ModelGlue, self.policy, self.request, updates={'age': '21'})
        finally:
            ModelGlue.authorize = original

        self.assertEqual(seen, [GlueOperationKind.REFRESH, GlueOperationKind.UPDATE])


class QuerySetRefreshTestCase(TestCase):
    def setUp(self):
        for index in range(7):
            Gorilla.objects.create(name=f'Gorilla {index:02d}')
        self.request = request_with_session()
        glue_object = QuerySetGlue(
            Gorilla.objects.all(),
            name='gorillas',
            access=GlueAccess.VIEW,
            fields=['name'],
            batch_size=3,
        )
        glue_object.request = self.request
        self.policy = glue_object.policy

    def test_refresh_re_runs_the_last_query_over_the_loaded_window(self):
        query = {'order_by': ['-name']}
        first, _introduced, policy = request_entry(
            QuerySetGlue, self.policy, self.request, attribute='query_with_params', kwargs=query,
        )
        _second, _introduced, policy = request_entry(
            QuerySetGlue,
            policy,
            self.request,
            attribute='query_with_params',
            kwargs={**query, 'seek_key': first['result']['seek_key']},
        )
        self.assertEqual(policy.state_snapshot['loaded_row_count'], 6)

        entry, introduced, refreshed = request_entry(QuerySetGlue, policy, self.request)

        self.assertEqual(len(entry['computed_data']['items']), 6)
        self.assertTrue(entry['computed_data']['has_next'])
        self.assertEqual(refreshed.state_snapshot, policy.state_snapshot)
        self.assertEqual(set(refreshed.children.values()), set(entry['computed_data']['items']))
        first_row = next(
            introduced_entry
            for introduced_entry in introduced
            if introduced_entry['address'] == entry['computed_data']['items'][0]
        )
        self.assertEqual(first_row['computed_data']['name'], 'Gorilla 06')

    def test_refresh_before_any_query_derives_the_first_batch(self):
        entry, _introduced, _refreshed = request_entry(QuerySetGlue, self.policy, self.request)

        self.assertEqual(len(entry['computed_data']['items']), 3)
