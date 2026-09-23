from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import cached_property
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import patch

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import F, QuerySet
from django.test import TestCase

if TYPE_CHECKING:
    from django.http import HttpRequest

from django_glue import Glue
from django_glue.access import GlueAccess
from django_glue.encoders import GlueResponseJSONEncoder
from django_glue.exceptions import (
    GlueCalledNonCallableAttributeError,
    GlueInvalidAttributeError,
    GlueInvalidPolicyError,
)
from django_glue.glue import (
    BaseGlue,
    FormGlue,
    FunctionGlue,
    GlueClassRegistry,
    GluePolicy,
    ModelGlue,
    QuerySetGlue,
    SequenceGlue,
)
from django_glue.glue.attributes import DeclaredAttribute
from django_glue.glue.attributes.definition import GlueAttributeKind
from django_glue.glue.options.django import (
    GlueRelatedModelChoices,
)
from django_glue.glue.queryset_unpickler import pickle_query
from django_glue.resolver.attribute_call.context import AttributeCallRequestContext
from django_glue.tests.glue.addressed_rows import addressed_row_entries
from test_project.fight.models import Fight
from test_project.gorilla.models import Gorilla, Skill
from test_project.test_forms import ContactForm, FightForm, TestModelForm

GORILLA_PATH = 'test_project.gorilla.models.Gorilla'


def request_with_session(session_key='test-session'):
    return SimpleNamespace(session=SimpleNamespace(session_key=session_key), FILES={})


def glue_context(name='gorilla', access=GlueAccess.CHANGE):
    return {
        'name': name,
        'access': access,
    }


def with_request(glue_object, session_key='test-session'):
    """Set a mock request on the glue object and return it."""
    glue_object.request = request_with_session(session_key)
    return glue_object


def policy_from_entry(entry):
    """Verify and decode the authoritative policy carried by an entry."""
    return GluePolicy.from_token(entry['policy_token'])


def policy_has_attribute(policy_or_dict, attribute_name):
    """Check if a policy has an attribute by name (handles nested policies).

    Works with both GluePolicy objects and serialized dicts.
    Handles 'form' as alias for 'forms.default'.
    """
    if hasattr(policy_or_dict, 'attributes'):
        attributes = policy_or_dict.attributes
    else:
        attributes = policy_or_dict.get('attributes', [])

    # 'form' is an alias for 'forms.default'
    if attribute_name == 'form':
        attribute_name = 'forms.default'

    for attr in attributes:
        if isinstance(attr, str):
            if attr == attribute_name:
                return True
        elif isinstance(attr, dict):
            # Serialized nested policy
            if attr.get('name', '').endswith(f'.{attribute_name}'):
                return True
        elif hasattr(attr, 'name'):
            # GluePolicy object
            if attr.name.endswith(f'.{attribute_name}'):
                return True
    return False


def policy_attribute_names(policy_or_dict):
    """Get attribute names from policy, extracting names from nested policies.

    Works with both GluePolicy objects and serialized dicts.
    """
    if hasattr(policy_or_dict, 'attributes'):
        attributes = policy_or_dict.attributes
    else:
        attributes = policy_or_dict.get('attributes', [])

    names = []
    for attr in attributes:
        if isinstance(attr, str):
            names.append(attr)
        elif isinstance(attr, dict):
            # Serialized nested policy - extract last part of name
            name = attr.get('name', '')
            names.append(name.split('.')[-1] if '.' in name else name)
        elif hasattr(attr, 'name'):
            # GluePolicy object - extract last part of name
            names.append(attr.name.split('.')[-1] if '.' in attr.name else attr.name)
    return names


class NestedStatsGlue(BaseGlue):
    namespace = 'stats'

    def __init__(self):
        super().__init__(name='stats', access=GlueAccess.VIEW)

    @property
    def identity(self) -> dict:
        return {'name': self.name}

    @cached_property
    def metadata(self) -> dict:
        return {
            'attributes': {
                name: attribute.metadata
                for name, attribute in self.attributes.items()
            },
        }

    @classmethod
    def _reconstruct_from_policy(cls, policy):
        return cls()

    @DeclaredAttribute(required_access=GlueAccess.VIEW)
    def score(self) -> int:
        return 42

    @DeclaredAttribute(required_access=GlueAccess.CHANGE)
    def reset(self) -> str:
        return 'reset'


class NestedDashboardGlue(BaseGlue):
    namespace = 'dashboard'

    def __init__(self):
        super().__init__(name='dashboard', access=GlueAccess.CHANGE)
        self.child_factory_calls = 0

    @Glue.property
    def stats(self) -> NestedStatsGlue:
        self.child_factory_calls += 1
        return NestedStatsGlue()

    @property
    def identity(self) -> dict:
        return {'name': self.name}

    @cached_property
    def metadata(self) -> dict:
        return {
            'attributes': {
                name: attribute.metadata
                for name, attribute in self.attributes.items()
            },
        }

    @classmethod
    def _reconstruct_from_policy(cls, policy):
        return cls()


class NamespaceDefaultGlue(BaseGlue):
    namespace = 'namespaceDefault'

    def __init__(self):
        super().__init__(access=GlueAccess.VIEW)

    @classmethod
    def _reconstruct_from_policy(cls, policy):
        return cls()


class CollectionDashboardGlue(BaseGlue):
    namespace = 'collectionDashboard'

    def __init__(self):
        super().__init__(name='collectionDashboard', access=GlueAccess.VIEW)

    @Glue.property
    def day_collection(self) -> SequenceGlue:
        return SequenceGlue([NestedStatsGlue()], name='internal_days')

    @classmethod
    def _reconstruct_from_policy(cls, policy):
        return cls()


class DescriptorDefaultGlue(BaseGlue):
    namespace = 'descriptorDefault'
    count = DeclaredAttribute(0, required_access=GlueAccess.VIEW)
    values = DeclaredAttribute(required_access=GlueAccess.VIEW, default_factory=list)

    def __init__(self):
        super().__init__(name='descriptorDefault', access=GlueAccess.VIEW)

    @classmethod
    def _reconstruct_from_policy(cls, policy):
        return cls()


class PlainService:
    pass


class DeclaredStateGlue(BaseGlue):
    namespace = 'declared_state'
    count = DeclaredAttribute(3, required_access=GlueAccess.VIEW)

    def __init__(self):
        super().__init__(name='declared_state', access=GlueAccess.CHANGE)

    @property
    def identity(self) -> dict:
        return {'name': self.name}

    @classmethod
    def _reconstruct_from_policy(cls, policy):
        return cls()


class InvalidServiceGlue(DeclaredStateGlue):
    service = DeclaredAttribute(PlainService(), required_access=GlueAccess.DELETE)


class GorillaCountingQuerySet(QuerySet):
    """QuerySet subclass with a @Glue.attr method, for QuerySetGlue.get_attribute_providers."""

    @DeclaredAttribute(required_access=GlueAccess.VIEW)
    def count_names_starting_with(self, letter: str) -> int:
        # `self` here must be this exact (already-filtered) queryset
        # instance, not Gorilla.objects.all() -- proves the method was
        # bound through QuerySetGlue's attribute_providers, not called
        # against a fresh, unfiltered manager.
        return self.filter(name__istartswith=letter).count()


class RawScore:
    def __init__(self, points: int):
        self.points = points


def _build_score_glue(raw_score: RawScore, *, name: str, access: GlueAccess) -> DeclaredStateGlue:
    glue_score = DeclaredStateGlue()
    glue_score.name = name
    glue_score.access = access
    glue_score.count = raw_score.points
    return glue_score


class SequenceAttributeGlue(BaseGlue):
    """Fixture for Glue.attr([])'s SequenceGlue adaptation of proxy-exposed items."""

    namespace = 'sequenceAttribute'

    scores: list[RawScore] = DeclaredAttribute([], glue_factory=_build_score_glue)
    already_glued: list[DeclaredStateGlue] = DeclaredAttribute([])

    def __init__(self):
        super().__init__(name='sequenceAttribute', access=GlueAccess.VIEW)

    @classmethod
    def _reconstruct_from_policy(cls, policy):
        return cls()


class AllFieldsTestCase(TestCase):
    """Tests for ALL_FIELDS constant behavior in ModelGlue and QuerySetGlue."""

    def setUp(self):
        self.gorilla = Gorilla.objects.create(
            name='Koko',
            description='Leader',
            age=18,
            weight=200.0,
            height=1.8,
        )

    def test_fields_or_exclude_list_containing_all_marker_raises_helpful_error(self):
        with self.assertRaisesRegex(ValueError, "fields contains '__all__' as an element"):
            ModelGlue(self.gorilla, **glue_context(), fields=['__all__'])
        with self.assertRaisesRegex(ValueError, "fields contains '__all__' as an element"):
            QuerySetGlue(
                Gorilla.objects.all(),
                **glue_context(name='gorillas', access=GlueAccess.VIEW),
                fields=['__all__'],
            )
        with self.assertRaisesRegex(ValueError, "exclude contains '__all__' as an element"):
            QuerySetGlue(
                Gorilla.objects.all(),
                **glue_context(name='gorillas', access=GlueAccess.VIEW),
                exclude=['__all__'],
            )

    def test_pk_always_included_with_explicit_fields(self):
        model = ModelGlue(self.gorilla, **glue_context(), fields=['name'])
        queryset = QuerySetGlue(
            Gorilla.objects.all(),
            **glue_context(name='gorillas', access=GlueAccess.VIEW),
            fields=['name'],
        )

        self.assertEqual(model._included_fields, ['id', 'name'])
        self.assertEqual(queryset._included_fields, ['id', 'name'])

    def test_queryset_pk_included_in_row_state(self):
        glue_object = with_request(QuerySetGlue(
            Gorilla.objects.all(),
            name='gorillas',
            access=GlueAccess.VIEW,
            fields=['name'],
        ))

        row = addressed_row_entries(glue_object, glue_object.query_with_params())[0]

        self.assertEqual(row['computed_data']['id'], self.gorilla.pk)

    def test_pk_not_included_when_explicitly_excluded(self):
        model = ModelGlue(self.gorilla, **glue_context(), fields=['name'], exclude=['id'])
        queryset = QuerySetGlue(
            Gorilla.objects.all(),
            **glue_context(name='gorillas', access=GlueAccess.VIEW),
            fields=['name'],
            exclude=['id'],
        )

        self.assertEqual(model._included_fields, ['name'])
        self.assertEqual(queryset._included_fields, ['name'])

    def test_model_all_fields_includes_all_model_fields(self):
        from django_glue.glue.objects.django.model.object import ALL_FIELDS

        glue_object = with_request(ModelGlue(
            self.gorilla,
            **glue_context(access=GlueAccess.VIEW),
            fields=ALL_FIELDS,
        ))

        included = glue_object._included_fields
        # Should include standard fields
        self.assertIn('name', included)
        self.assertIn('description', included)
        self.assertIn('age', included)
        self.assertIn('weight', included)
        self.assertIn('height', included)
        self.assertIn('id', included)
        # Should NOT include binary fields (globally excluded)
        self.assertNotIn('signature', included)

    def test_model_all_fields_excludes_binary_fields_silently(self):
        from django_glue.glue.objects.django.model.object import ALL_FIELDS

        # Should not raise an error even though the model has a BinaryField
        glue_object = ModelGlue(
            self.gorilla,
            **glue_context(access=GlueAccess.VIEW),
            fields=ALL_FIELDS,
        )

        self.assertNotIn('signature', glue_object._included_fields)
        self.assertNotIn('signature', glue_object.attributes)

    def test_model_all_fields_with_exclude(self):
        from django_glue.glue.objects.django.model.object import ALL_FIELDS

        glue_object = ModelGlue(
            self.gorilla,
            **glue_context(access=GlueAccess.VIEW),
            fields=ALL_FIELDS,
            exclude=['description', 'age'],
        )

        included = glue_object._included_fields
        self.assertIn('name', included)
        self.assertNotIn('description', included)
        self.assertNotIn('age', included)

    def test_model_exclude_all_fields(self):
        from django_glue.glue.objects.django.model.object import ALL_FIELDS

        glue_object = ModelGlue(
            self.gorilla,
            **glue_context(access=GlueAccess.VIEW),
            exclude=ALL_FIELDS,
        )

        # All model fields should be excluded
        self.assertEqual(glue_object._included_fields, [])

    def test_model_fields_with_exclude_all_fields(self):
        from django_glue.glue.objects.django.model.object import ALL_FIELDS

        glue_object = ModelGlue(
            self.gorilla,
            **glue_context(access=GlueAccess.VIEW),
            fields=['name', 'age'],
            exclude=ALL_FIELDS,
        )

        # Explicit fields minus all fields = empty
        self.assertEqual(glue_object._included_fields, [])

    def test_queryset_all_fields_includes_all_model_fields(self):
        from django_glue.glue.objects.django.model.object import ALL_FIELDS

        glue_object = QuerySetGlue(
            Gorilla.objects.all(),
            **glue_context(name='gorillas', access=GlueAccess.VIEW),
            fields=ALL_FIELDS,
        )

        included = glue_object._included_fields
        self.assertIn('name', included)
        self.assertIn('description', included)
        self.assertIn('age', included)
        # Should NOT include binary fields
        self.assertNotIn('signature', included)

    def test_queryset_all_fields_with_exclude(self):
        from django_glue.glue.objects.django.model.object import ALL_FIELDS

        glue_object = QuerySetGlue(
            Gorilla.objects.all(),
            **glue_context(name='gorillas', access=GlueAccess.VIEW),
            fields=ALL_FIELDS,
            exclude=['description', 'age'],
        )

        included = glue_object._included_fields
        self.assertIn('name', included)
        self.assertNotIn('description', included)
        self.assertNotIn('age', included)

    def test_queryset_exclude_all_fields(self):
        from django_glue.glue.objects.django.model.object import ALL_FIELDS

        glue_object = QuerySetGlue(
            Gorilla.objects.all(),
            **glue_context(name='gorillas', access=GlueAccess.VIEW),
            exclude=ALL_FIELDS,
        )

        self.assertEqual(glue_object._included_fields, [])

    def test_all_fields_is_exported_from_main_module(self):
        from django_glue import ALL_FIELDS

        self.assertEqual(ALL_FIELDS, '__all__')

    def test_model_all_fields_builds_valid_state(self):
        from django_glue.glue.objects.django.model.object import ALL_FIELDS

        glue_object = with_request(ModelGlue(
            self.gorilla,
            **glue_context(access=GlueAccess.VIEW),
            fields=ALL_FIELDS,
        ))

        state = glue_object.state
        self.assertEqual(state['name']['value'], 'Koko')
        self.assertEqual(state['age']['value'], 18)
        self.assertNotIn('signature', state)

    def test_model_all_fields_builds_valid_metadata(self):
        from django_glue.glue.objects.django.model.object import ALL_FIELDS

        glue_object = with_request(ModelGlue(
            self.gorilla,
            **glue_context(access=GlueAccess.VIEW),
            fields=ALL_FIELDS,
        ))

        fields = glue_object.get_static_data()['fields']
        self.assertIn('name', fields)
        self.assertIn('age', fields)
        self.assertNotIn('signature', fields)

    def test_queryset_all_fields_query_returns_valid_payloads(self):
        from django_glue.glue.objects.django.model.object import ALL_FIELDS

        glue_object = QuerySetGlue(
            Gorilla.objects.all(),
            name='gorillas',
            access=GlueAccess.VIEW,
            fields=ALL_FIELDS,
        )
        glue_object.request = request_with_session()
        glue_object.policy  # Build policy

        result = glue_object.query_with_params()

        self.assertEqual(len(result['items']), 1)
        row = addressed_row_entries(glue_object, result)[0]
        self.assertEqual(row['computed_data']['name'], 'Koko')
        self.assertNotIn('signature', row['computed_data'])

    def test_queryset_all_fields_uses_fk_attnames(self):
        from django_glue.glue.objects.django.model.object import ALL_FIELDS

        red_gorilla = Gorilla.objects.create(name='Red Koko')
        blue_gorilla = Gorilla.objects.create(name='Blue Bobo')
        Fight.objects.create(
            name='Championship',
            red_corner=red_gorilla,
            blue_corner=blue_gorilla,
        )
        glue_object = QuerySetGlue(
            Fight.objects.all(),
            name='fights',
            access=GlueAccess.VIEW,
            fields=ALL_FIELDS,
        )
        glue_object.request = request_with_session()
        glue_object.policy

        result = glue_object.query_with_params()

        row = addressed_row_entries(glue_object, result)[0]
        self.assertIn('red_corner_id', row['computed_data'])
        self.assertNotIn('red_corner', row['computed_data'])

    def test_queryset_all_fields_does_not_traverse_prefetch_related_relations(self):
        from django_glue.glue.objects.django.model.object import ALL_FIELDS

        gorilla = Gorilla.objects.create(name='Koko')
        gorilla.skills.add(Skill.objects.create(name='Grappling'))
        glue_object = with_request(QuerySetGlue(
            Gorilla.objects.prefetch_related('skills'),
            name='gorillas',
            access=GlueAccess.VIEW,
            fields=ALL_FIELDS,
        ))

        self.assertEqual(glue_object._projected_relations, ())
        row = addressed_row_entries(glue_object, glue_object.query_with_params())[0]
        self.assertEqual(GluePolicy.from_token(row['policy_token']).children, {})

    def test_queryset_all_fields_does_not_traverse_select_related_relations(self):
        from django_glue.glue.objects.django.model.object import ALL_FIELDS

        red_gorilla = Gorilla.objects.create(name='Red Koko')
        blue_gorilla = Gorilla.objects.create(name='Blue Bobo')
        Fight.objects.create(
            name='Championship',
            red_corner=red_gorilla,
            blue_corner=blue_gorilla,
        )
        glue_object = QuerySetGlue(
            Fight.objects.select_related('red_corner'),
            name='fights',
            access=GlueAccess.VIEW,
            fields=ALL_FIELDS,
        )
        glue_object.request = request_with_session()
        glue_object.policy

        self.assertIn('red_corner_id', glue_object._included_fields)
        self.assertNotIn('red_corner', glue_object._included_fields)
        self.assertIn('blue_corner_id', glue_object._included_fields)
        self.assertNotIn('blue_corner', glue_object._included_fields)

        result = glue_object.query_with_params()

        row = addressed_row_entries(glue_object, result)[0]
        self.assertIn('red_corner_id', row['computed_data'])
        self.assertNotIn('red_corner', row['computed_data'])
        self.assertIn('blue_corner_id', row['computed_data'])
        self.assertNotIn('blue_corner', row['computed_data'])


class GluePolicyTestCase(TestCase):
    def test_base_glue_defaults_name_to_namespace(self):
        glue_object = with_request(NamespaceDefaultGlue())

        policy = glue_object.policy

        self.assertEqual(policy.name, 'namespaceDefault')
        self.assertEqual(policy.namespace, 'namespaceDefault')

    def test_declared_attribute_defaults_are_instance_values(self):
        first = DescriptorDefaultGlue()
        second = DescriptorDefaultGlue()

        first.values.append('first')
        first.count = 2

        self.assertEqual(first.values, ['first'])
        self.assertEqual(second.values, [])
        self.assertEqual(first.count, 2)
        self.assertEqual(second.count, 0)

    def test_child_factory_builds_independent_children_per_owner(self):
        first = with_request(CollectionDashboardGlue())
        second = with_request(CollectionDashboardGlue())

        first_child = first._bound_children[0].glue_object
        second_child = second._bound_children[0].glue_object

        self.assertIsNot(first_child, second_child)
        self.assertIsNot(first_child.items[0], second_child.items[0])

    def test_list_assignment_of_already_glued_items_becomes_collection(self):
        glue_object = SequenceAttributeGlue()

        glue_object.already_glued = [DeclaredStateGlue(), DeclaredStateGlue()]

        self.assertIsInstance(glue_object.already_glued, SequenceGlue)
        self.assertEqual(len(glue_object.already_glued.items), 2)

    def test_list_assignment_of_raw_items_uses_glue_factory(self):
        glue_object = SequenceAttributeGlue()

        glue_object.scores = [RawScore(10), RawScore(20)]

        self.assertIsInstance(glue_object.scores, SequenceGlue)
        self.assertEqual([item.count for item in glue_object.scores.items], [10, 20])
        self.assertTrue(all(isinstance(item, DeclaredStateGlue) for item in glue_object.scores.items))

    def test_empty_list_assignment_is_not_wrapped(self):
        glue_object = SequenceAttributeGlue()

        glue_object.scores = []

        self.assertEqual(glue_object.scores, [])

    def test_list_mixing_glue_and_raw_items_without_glue_factory_raises(self):
        glue_object = SequenceAttributeGlue()

        with self.assertRaises(TypeError):
            glue_object.already_glued = [DeclaredStateGlue(), RawScore(10)]

    def test_list_without_glue_items_or_factory_stays_plain_data(self):
        glue_object = SequenceAttributeGlue()

        glue_object.already_glued = [1, 2, 3]

        self.assertEqual(glue_object.already_glued, [1, 2, 3])

    def test_auto_wrapped_collection_and_items_inherit_instance_access(self):
        """Regression test: items built by glue_factory must carry the owning
        instance's runtime access (e.g. CHANGE/DELETE for a permitted user),
        not the Glue.attr(...) descriptor's own declared required_access
        (which defaults to VIEW and only gates the attribute itself)."""
        glue_object = SequenceAttributeGlue()
        glue_object.access = GlueAccess.DELETE

        glue_object.scores = [RawScore(10)]

        self.assertEqual(glue_object.scores.access, GlueAccess.DELETE)
        self.assertEqual(glue_object.scores.items[0].access, GlueAccess.DELETE)

    def test_child_factory_runs_once_while_building_policy(self):
        glue_object = with_request(NestedDashboardGlue())
        _ = glue_object.policy

        self.assertEqual(glue_object.child_factory_calls, 1)

    def test_nested_glue_object_name_comes_from_attribute_path(self):
        glue_object = with_request(CollectionDashboardGlue())

        policy = glue_object.policy
        children = glue_object._bound_children

        self.assertEqual(policy.children, {
            'day_collection': f'{glue_object.address}.day_collection',
        })
        self.assertNotIn('day_collection', policy.attributes)
        self.assertEqual(len(children), 1)
        self.assertIsInstance(children[0].glue_object, SequenceGlue)

    def test_collection_policy_contains_ordered_item_refs(self):
        second_item = DeclaredStateGlue()
        glue_object = with_request(SequenceGlue(
            [
                NestedStatsGlue(),
                second_item,
            ],
            name='dashboard_items',
            access=GlueAccess.VIEW,
        ))

        policy = glue_object.policy

        self.assertEqual(policy.namespace, 'sequence')
        self.assertEqual(policy.identity, {'item_keys': ['stats', 'declared_state']})

        items = glue_object.state['items']
        entries = glue_object._serialized_child_entries()
        item_policies = [GluePolicy.from_token(entry['policy_token']) for entry in entries]
        self.assertEqual(items, [entry['address'] for entry in entries])
        self.assertEqual(
            [item_policy.namespace for item_policy in item_policies],
            ['stats', 'declared_state'],
        )
        self.assertEqual(
            [item_policy.name for item_policy in item_policies],
            ['stats', 'declared_state'],
        )
        self.assertEqual(entries[0]['computed_data'], {})
        self.assertEqual(
            GluePolicy.from_token(entries[1]['policy_token']).state_snapshot,
            {'count': 3},
        )

    def test_sequence_reconstruction_preserves_item_keys(self):
        glue_object = with_request(SequenceGlue(
            [
                NestedStatsGlue(),
                DeclaredStateGlue(),
            ],
            name='dashboard_items',
            access=GlueAccess.VIEW,
        ))
        policy = glue_object.policy

        resolved = SequenceGlue._reconstruct_from_policy(policy)

        self.assertEqual(resolved.get_identity(), {'item_keys': ['stats', 'declared_state']})
        self.assertEqual(resolved.get_identity(), glue_object.get_identity())

    def test_registered_collection_registers_collection_only(self):
        request = request_with_session()

        collection = Glue.object(request, SequenceGlue(
            [NestedStatsGlue(), DeclaredStateGlue()],
            name='dashboard_items',
            access=GlueAccess.VIEW,
        ))

        registered = request.__dict__['__glue_manifest__']

        self.assertEqual([glue_object.name for glue_object in registered], ['dashboard_items'])
        entries = collection._serialized_child_entries()
        self.assertEqual(collection.state['items'], [entry['address'] for entry in entries])
        item_policies = [GluePolicy.from_token(entry['policy_token']) for entry in entries]
        self.assertEqual([item_policy.name for item_policy in item_policies], ['stats', 'declared_state'])

    def test_policy_token_restores_without_preserving_proxy_policy_shape(self):
        policy = GluePolicy.new_signed_policy({
            'session_id': 'test-session',
            'request_user_id': None,
            'name': 'gorilla',
            'namespace': 'model',
            'identity': {'model_class_path': 'test_project.gorilla.models.Gorilla', 'target_pk': 1},
            'access': GlueAccess.VIEW,
            'attributes': ['name'],
        })

        payload = policy.model_dump()
        restored = GluePolicy.from_token(policy.token)

        self.assertEqual(restored.namespace, 'model')
        self.assertIn('identity', payload)
        self.assertIn('attributes', payload)
        self.assertNotIn('subject_details', payload)
        self.assertNotIn('bound_attributes', payload)

    def test_policy_token_serializes_datetime_identity(self):
        policy = GluePolicy.new_signed_policy({
            'session_id': 'test-session',
            'request_user_id': None,
            'name': 'agreement_form',
            'namespace': 'form',
            'identity': {
                'initial': {
                    'sent_datetime': datetime(2026, 8, 14, 12, 30, tzinfo=timezone.utc),
                },
            },
            'access': GlueAccess.CHANGE,
            'attributes': ['sent_datetime'],
        })

        restored = GluePolicy.from_token(policy.token)

        self.assertEqual(restored.identity['initial']['sent_datetime'], '2026-08-14T12:30:00Z')


class DeclaredAttributeDefaultAccessTestCase(TestCase):
    def test_required_access_defaults_to_view_when_omitted(self):
        @DeclaredAttribute
        def load(self):
            return 'loaded'

        self.assertEqual(load.__glue_options__.required_access, GlueAccess.VIEW)

    def test_required_access_can_still_be_overridden(self):
        @DeclaredAttribute(required_access=GlueAccess.CHANGE)
        def save(self):
            return 'saved'

        self.assertEqual(save.__glue_options__.required_access, GlueAccess.CHANGE)

    def test_render_as_html_defaults_to_false(self):
        @DeclaredAttribute
        def load(self):
            return 'loaded'

        self.assertFalse(load.__glue_options__.render_as_html)

    def test_render_as_html_can_be_set(self):
        @DeclaredAttribute(render_as_html=True)
        def render_panel(self):
            return 'rendered'

        self.assertTrue(render_panel.__glue_options__.render_as_html)

    def test_html_attr_shortcut_sets_render_as_html(self):
        @Glue.html_attr
        def render_panel(self):
            return 'rendered'

        self.assertTrue(render_panel.__glue_options__.render_as_html)
        self.assertEqual(render_panel.__glue_options__.required_access, GlueAccess.VIEW)

    def test_html_attr_shortcut_accepts_other_kwargs(self):
        @Glue.html_attr(required_access=GlueAccess.CHANGE)
        def render_editable_panel(self):
            return 'rendered'

        self.assertTrue(render_editable_panel.__glue_options__.render_as_html)
        self.assertEqual(render_editable_panel.__glue_options__.required_access, GlueAccess.CHANGE)


class TemplateResponseAttributeGlue(BaseGlue):
    """Fixture: a callable attribute returning a TemplateResponse, with and without render_as_html."""

    namespace = 'templateResponseAttribute'

    def __init__(self):
        super().__init__(name='templateResponseAttribute', access=GlueAccess.VIEW)

    @DeclaredAttribute
    def render_plain(self, request: 'HttpRequest'):
        from django.template.response import TemplateResponse
        return TemplateResponse(request, 'glue_template_test.html', {'greeting': 'Plain text'})

    @Glue.html_attr
    def render_html(self, request: 'HttpRequest'):
        from django.template.response import TemplateResponse
        return TemplateResponse(request, 'glue_template_test.html', {'greeting': 'Coerced'})

    @classmethod
    def _reconstruct_from_policy(cls, policy):
        return cls()


class TemplateResponseAttributeTestCase(TestCase):
    """Attribute-call-level coverage for the render_as_html opt-in (see also test_response.py)."""

    def _call(self, glue_object, attribute_name):
        from django.test import RequestFactory

        request = RequestFactory().get('/')
        request.session = SimpleNamespace(session_key='test-session')
        glue_object.request = request

        context = AttributeCallRequestContext.model_construct(
            request=request,
            target_glue_policy=glue_object.policy,
            target_glue_updates={},
            target_attribute_name=attribute_name,
            target_attribute_call_kwargs={},
        )
        entry, _introduced = glue_object.process_attribute_call(context)
        return entry

    def test_template_response_sent_as_raw_text_without_render_as_html(self):
        payload = self._call(TemplateResponseAttributeGlue(), 'render_plain')

        self.assertIsInstance(payload['result'], str)
        self.assertIn('Plain text', payload['result'])

    def test_template_response_coerced_to_glue_template_response_with_html_attr(self):
        payload = self._call(TemplateResponseAttributeGlue(), 'render_html')

        self.assertIn('Coerced', payload['html'])


class DjangoModelGlueObjectTestCase(TestCase):
    def setUp(self):
        self.gorilla = Gorilla.objects.create(
            name='Koko',
            description='Leader',
            age=18,
            weight=200.0,
            height=1.8,
        )

    def test_model_field_adapter_marks_non_editable_fields_read_only(self):
        glue_object = ModelGlue(
            self.gorilla,
            **glue_context(access=GlueAccess.VIEW),
            fields=['created_at'],
        )
        attribute = glue_object.attributes['created_at']

        self.assertEqual(attribute.definition.required_access, GlueAccess.VIEW)
        schema = attribute.schema()
        self.assertEqual(schema['type'], 'DateTimeField')
        self.assertFalse(schema['editable'])

    def test_model_adapter_excludes_globally_excluded_fields(self):
        glue_object = ModelGlue(
            self.gorilla,
            **glue_context(access=GlueAccess.VIEW),
            exclude=['id'],
        )

        self.assertNotIn('signature', glue_object.attributes)
        self.assertNotIn('signature', glue_object.state)
        self.assertNotIn(
            'signature',
            glue_object.get_static_data()['fields'],
        )

    def test_model_adapter_rejects_explicitly_excluded_field_types(self):
        with self.assertRaisesRegex(ValueError, 'Binary fields'):
            ModelGlue(
                self.gorilla,
                **glue_context(access=GlueAccess.VIEW),
                fields=['name', 'signature'],
            )

    def test_model_adapter_requires_fields_or_exclude(self):
        with self.assertRaisesRegex(ValueError, 'ModelGlue requires at least one of fields or exclude'):
            ModelGlue(
                self.gorilla,
                **glue_context(access=GlueAccess.VIEW),
            )

    def test_model_adapter_builds_policy_state_and_metadata(self):
        glue_object = with_request(ModelGlue(
            self.gorilla,
            **glue_context(),
            fields=['id', 'name', 'created_at'],
        ))
        policy = glue_object.policy
        static_data = glue_object.get_static_data()

        self.assertEqual(policy.namespace, 'model')
        self.assertEqual(policy.identity['target_pk'], self.gorilla.pk)
        self.assertIn('save', policy.attributes)
        self.assertIn('delete', policy.attributes)
        self.assertEqual(policy.state_snapshot['name'], 'Koko')
        self.assertEqual(static_data['fields']['name']['type'], 'CharField')
        self.assertFalse(static_data['fields']['name']['disabled'])
        self.assertEqual(static_data['fields']['created_at']['type'], 'DateTimeField')
        self.assertTrue(static_data['fields']['created_at']['disabled'])

    def test_model_relation_field_metadata_has_stable_choice_shape(self):
        glue_object = ModelGlue(self.gorilla, **glue_context(), fields=['skills'])

        schema = glue_object.attributes['skills'].schema()

        self.assertEqual(schema['type'], 'ManyToManyField')
        self.assertEqual(schema['namespace'], 'field')
        self.assertEqual(schema['related_model'], 'test_project.gorilla.models.Skill')
        self.assertIn('choices', schema)

    def test_model_foreign_key_choices_returns_related_choices(self):
        skill = Skill.objects.create(name='Grappling')
        glue_object = ModelGlue(self.gorilla, **glue_context(), fields=['skills'])

        result = glue_object.foreign_key_choices(field_name='skills')

        self.assertEqual(result['results'], [{
            'value': skill.pk,
            'label': 'Grappling',
            'obj': {'pk': skill.pk, '__str__': 'Grappling'},
        }])

    def test_model_foreign_key_choices_uses_registered_choice_queryset(self):
        Skill.objects.create(name='Hidden')
        visible = Skill.objects.create(name='Visible', difficulty=4)
        choice_queryset = Glue.choices(
            Skill.objects.filter(name='Visible'),
            search_fields=['name', 'description'],
            fields=['name', 'difficulty'],
        )
        glue_object = ModelGlue(
            self.gorilla,
            **glue_context(),
            fields=['skills'],
            choices={'skills': choice_queryset},
        )

        result = glue_object.foreign_key_choices(
            field_name='skills',
            search='vis',
        )

        self.assertEqual(result['results'], [{
            'value': visible.pk,
            'label': 'Visible',
            'obj': {
                'pk': visible.pk,
                '__str__': 'Visible',
                'name': 'Visible',
                'difficulty': 4,
            },
        }])

    def test_registered_choice_queryset_survives_policy_reconstruction(self):
        visible = Skill.objects.create(name='Visible')
        Skill.objects.create(name='Hidden')
        glue_object = with_request(ModelGlue(
            self.gorilla,
            **glue_context(),
            fields=['skills'],
            choices={
                'skills': Glue.choices(
                    Skill.objects.filter(name='Visible'),
                    fields=['name'],
                ),
            },
        ))

        restored = ModelGlue._reconstruct_from_policy(glue_object.policy)
        result = restored.foreign_key_choices(field_name='skills')

        self.assertEqual(
            [choice['value'] for choice in result['results']],
            [visible.pk],
        )
        self.assertEqual(result['results'][0]['obj']['name'], 'Visible')

    def test_searchable_registered_choice_queryset_survives_policy_reconstruction(self):
        matching = Skill.objects.create(name='Grappling')
        Skill.objects.create(name='Striking')
        glue_object = with_request(ModelGlue(
            self.gorilla,
            **glue_context(),
            fields=['skills'],
            choices={
                'skills': Glue.choices(
                    Skill.objects.all(),
                    search_fields=['name'],
                    fields=['name'],
                ),
            },
        ))

        restored = ModelGlue._reconstruct_from_policy(glue_object.policy)

        # Searchability (the QuerySetChoiceOptions on the Query) must survive the
        # pickle round trip: an unfiltered first page without a query, filtered
        # results with one.
        self.assertEqual(
            len(restored.foreign_key_choices(field_name='skills')['results']),
            Skill.objects.count(),
        )
        searched = restored.foreign_key_choices(field_name='skills', search='grap')
        self.assertEqual(
            [choice['value'] for choice in searched['results']],
            [matching.pk],
        )

    def test_tampered_choice_queryset_policy_is_rejected_before_deserialization(self):
        glue_object = with_request(ModelGlue(
            self.gorilla,
            **glue_context(),
            fields=['skills'],
            choices={'skills': Glue.choices(Skill.objects.all())},
        ))

        with (
            patch(
                'django_glue.glue.objects.django.model_fields.unpickle_query'
            ) as deserialize_query,
            self.assertRaises(GlueInvalidPolicyError),
        ):
            verified_policy = GluePolicy.from_token(f'{glue_object.policy.token}x')
            ModelGlue._reconstruct_from_policy(verified_policy)

        deserialize_query.assert_not_called()

    def test_implicit_choice_source_loads_a_bounded_table(self):
        skill = Skill.objects.create(name='Grappling')
        glue_object = with_request(ModelGlue(self.gorilla, **glue_context(), fields=['skills']))

        result = glue_object.foreign_key_choices(field_name='skills', search='ignored')

        self.assertEqual([choice['value'] for choice in result['results']], [skill.pk])
        self.assertEqual(result['results'][0]['obj'], {'pk': skill.pk, '__str__': 'Grappling'})

    def test_implicit_choice_source_over_the_limit_is_a_declaration_error(self):
        from django.core.exceptions import ImproperlyConfigured

        from django_glue.glue.options.django import DEFAULT_SEARCH_LIMIT

        Skill.objects.bulk_create(
            Skill(name=f'Skill {index}') for index in range(DEFAULT_SEARCH_LIMIT + 1)
        )
        glue_object = with_request(ModelGlue(self.gorilla, **glue_context(), fields=['skills']))

        with self.assertRaisesRegex(ImproperlyConfigured, "'skills'.*Glue.choices"):
            glue_object.foreign_key_choices(field_name='skills')

        configured = with_request(ModelGlue(
            self.gorilla,
            **glue_context(),
            fields=['skills'],
            choices={'skills': Glue.choices(Skill.objects.all(), search_fields=['name'])},
        ))
        self.assertEqual(
            len(configured.foreign_key_choices(field_name='skills')['results']),
            DEFAULT_SEARCH_LIMIT,
        )

    def test_registered_choice_queryset_validates_relation_and_model(self):
        with self.assertRaisesRegex(ValueError, 'not an exposed relation'):
            ModelGlue(
                self.gorilla,
                **glue_context(),
                fields=['skills'],
                choices={'missing': Skill.objects.all()},
            )

        with self.assertRaisesRegex(ValueError, 'not an exposed relation'):
            ModelGlue(
                self.gorilla,
                **glue_context(),
                fields=['name'],
                choices={'skills': Skill.objects.all()},
            )

        with self.assertRaisesRegex(ValueError, 'must query'):
            ModelGlue(
                self.gorilla,
                **glue_context(),
                fields=['skills'],
                choices={'skills': Gorilla.objects.all()},
            )

    def test_model_foreign_key_choices_returns_configured_choices(self):
        skill = Skill.objects.create(name='Grappling')
        glue_object = with_request(ModelGlue(
            self.gorilla,
            **glue_context(),
            fields=['skills'],
        ))
        context = AttributeCallRequestContext.model_construct(
            request=glue_object.request,
            target_glue_policy=glue_object.policy,
            target_glue_updates={'skills': []},
            target_attribute_name='foreign_key_choices',
            target_attribute_call_kwargs={'field_name': 'skills'},
        )

        payload, _introduced = glue_object.process_attribute_call(context)

        self.assertEqual(
            [choice['value'] for choice in payload['result']['results']],
            [skill.pk],
        )

    def test_model_save_normalizes_rich_relation_and_file_state(self):
        skill = Skill.objects.create(name='Grappling')
        glue_object = with_request(ModelGlue(
            self.gorilla,
            **glue_context(),
            fields=['name', 'age', 'weight', 'height', 'profile_photo', 'skills'],
        ))

        # Load retained state before save (normally done during object resolution)
        glue_object._load_client_state({
            'name': 'Ndume',
            'age': 22,
            'weight': 162.2,
            'height': 1.5,
            'skills': [skill.pk],
        })

        result = glue_object.save()

        self.gorilla.refresh_from_db()
        self.assertTrue(result['success'])
        self.assertEqual(self.gorilla.name, 'Ndume')
        self.assertEqual(list(self.gorilla.skills.all()), [skill])

    def test_model_save_persists_nested_state_file_upload(self):
        request = request_with_session()
        request.FILES = {
            'profile_photo': SimpleUploadedFile(
                'profile-photo.gif',
                b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;',
                content_type='image/gif',
            )
        }
        glue_object = ModelGlue(
            self.gorilla,
            **glue_context(),
            fields=['name', 'age', 'weight', 'height', 'profile_photo'],
        )
        glue_object.request = request

        # Load retained state before save (normally done during object resolution)
        glue_object._load_client_state({
            'name': self.gorilla.name,
            'age': self.gorilla.age,
            'weight': self.gorilla.weight,
            'height': self.gorilla.height,
        })

        result = glue_object.save()

        self.gorilla.refresh_from_db()
        self.assertTrue(result['success'])
        self.assertTrue(self.gorilla.profile_photo)
        self.assertTrue(self.gorilla.profile_photo.name.startswith('gorilla_photos/profile-photo'))

    def test_model_adapter_serializes_file_field_values_for_initial_state(self):
        self.gorilla.profile_photo.save(
            'profile-photo.png',
            ContentFile(b'image-bytes'),
            save=True,
        )
        glue_object = with_request(ModelGlue(
            self.gorilla,
            **glue_context(access=GlueAccess.VIEW),
            fields=['profile_photo'],
        ))

        # Simulate the actual HTTP flow: state is JSON-encoded before being sent to frontend
        state = json.loads(json.dumps(glue_object.state, cls=GlueResponseJSONEncoder))

        file_value = state['profile_photo']['value']
        self.assertTrue(file_value['name'].startswith('gorilla_photos/profile-photo'))
        self.assertTrue(file_value['url'].startswith('/media/gorilla_photos/profile-photo'))
        self.assertIn('path', file_value)  # Local storage supports path
        self.assertNotIn('size', file_value)  # Size is omitted for performance

    def test_model_adapter_reconstructs_model_reconstruct_from_policy(self):
        glue_object = with_request(ModelGlue(
            self.gorilla,
            **glue_context(access=GlueAccess.VIEW),
            fields=['id', 'name'],
        ))
        policy = glue_object.policy

        resolved = ModelGlue._reconstruct_from_policy(policy)

        self.assertEqual(resolved.instance, self.gorilla)

    def test_model_with_computed_attributes_adds_attribute_to_payload(self):
        glue_object = with_request(ModelGlue(
            self.gorilla,
            **glue_context(access=GlueAccess.VIEW),
            fields=['id', 'name'],
            computed_attributes={'badge_data': gorilla_badge_data},
        ))

        policy = glue_object.policy
        static_data = glue_object.get_static_data()

        self.assertIn('badge_data', policy.attributes)
        self.assertIn('badge_data', static_data['fields'])
        self.assertEqual(
            glue_object.get_computed_data(include_all=True)['badge_data'],
            {'label': 'KOKO'},
        )
        self.assertTrue(
            policy.identity['computed_attributes']['badge_data']['path'].endswith(
                'test_objects.gorilla_badge_data'
            )
        )

    def test_model_with_computed_attributes_supports_kwargs(self):
        glue_object = with_request(ModelGlue(
            self.gorilla,
            **glue_context(access=GlueAccess.VIEW),
            fields=['id', 'name'],
            computed_attributes={
                'badge_data': (gorilla_badge_data_with_suffix, {'suffix': '!'}),
            },
        ))

        state = glue_object.state

        self.assertEqual(state['badge_data']['value'], {'label': 'KOKO!'})
        self.assertEqual(
            glue_object.policy.identity['computed_attributes']['badge_data']['kwargs'],
            {'suffix': '!'},
        )

    def test_model_computed_attributes_survive_policy_reconstruction(self):
        glue_object = with_request(ModelGlue(
            self.gorilla,
            **glue_context(access=GlueAccess.VIEW),
            fields=['id', 'name'],
            computed_attributes={'badge_data': gorilla_badge_data},
        ))

        resolved = ModelGlue._reconstruct_from_policy(glue_object.policy)
        resolved.request = glue_object.request

        self.assertEqual(resolved.state['badge_data']['value'], {'label': 'KOKO'})

    def test_model_with_computed_attributes_rejects_non_importable_callables(self):
        with self.assertRaisesRegex(ValueError, 'importable top-level callables'):
            ModelGlue(
                self.gorilla,
                **glue_context(access=GlueAccess.VIEW),
                fields=['id', 'name'],
                computed_attributes={'badge_data': lambda gorilla: gorilla.name},
            )

    def test_model_shortcut_accepts_computed_attributes(self):
        request = request_with_session()

        glue_object = Glue.model(
            target=self.gorilla,
            request=request,
            unique_name='gorilla',
            access=Glue.Access.VIEW,
            fields=['id', 'name'],
            computed_attributes={'badge_data': gorilla_badge_data},
        )

        entry_policy = policy_from_entry(glue_object.entry.model_dump())
        self.assertEqual(entry_policy.namespace, 'model')
        self.assertIn('badge_data', entry_policy.attributes)

    def test_model_adapter_transfers_target_glue_attributes_to_policy(self):
        glue_object = with_request(ModelGlue(self.gorilla, **glue_context(), fields=['id', 'name']))
        policy = glue_object.policy

        self.assertIn('shout', policy.attributes)
        self.assertIn('services.increment_age', policy.attributes)
        self.assertNotIn('services', policy.attributes)
        self.assertEqual(
            glue_object._attribute_registry.get('services').kind,
            GlueAttributeKind.NAMESPACE,
        )
        self.assertEqual(
            glue_object._attribute_registry.get('services.increment_age').kind,
            GlueAttributeKind.CALLABLE,
        )

        # Call the shout method directly on the instance
        shout_result = self.gorilla.shout(volume=5)

        self.assertEqual(shout_result, 'AAAAA')

    def test_model_form_class_exposes_default_form_glue_attributes(self):
        glue_object = with_request(ModelGlue(
            self.gorilla,
            **glue_context(),
            fields=['id', 'name'],
            form=TestModelForm(instance=self.gorilla),
        ))

        policy = glue_object.policy
        children = glue_object._bound_children

        self.assertEqual(policy.children, {
            'form': f'{glue_object.address}.form',
        })
        self.assertNotIn('form', policy.attributes)
        self.assertEqual(len(children), 1)
        self.assertIsInstance(children[0].glue_object, FormGlue)
        self.assertEqual(children[0].glue_object.form['name'].value(), 'Koko')

    def test_model_form_classes_exposes_named_forms(self):
        glue_object = with_request(ModelGlue(
            self.gorilla,
            **glue_context(),
            fields=['id', 'name'],
            forms={'edit': TestModelForm(instance=self.gorilla)},
        ))

        policy = glue_object.policy
        self.assertNotIn('form', policy.children)
        self.assertEqual(
            policy.children['forms.edit'],
            f'{glue_object.address}.forms.edit',
        )
        self.assertEqual(
            glue_object._attribute_registry.get('forms').kind,
            GlueAttributeKind.NAMESPACE,
        )

    def test_model_rejects_duplicate_default_form_class(self):
        with self.assertRaisesRegex(ValueError, 'form'):
            ModelGlue(
                self.gorilla,
                **glue_context(),
                fields=['id', 'name'],
                form=TestModelForm(instance=self.gorilla),
                forms={'default': TestModelForm(instance=self.gorilla)},
            )

    def test_model_without_forms_keeps_existing_attribute_shape(self):
        glue_object = with_request(ModelGlue(self.gorilla, **glue_context(), fields=['id', 'name']))

        self.assertNotIn('form_identities', glue_object.policy.identity)
        self.assertFalse(policy_has_attribute(glue_object.policy, 'form'))
        self.assertFalse(policy_has_attribute(glue_object.policy, 'forms.default'))

    def test_model_form_class_can_be_passed_instead_of_instance(self):
        """Verify that a form class can be passed instead of a form instance."""
        glue_object = with_request(ModelGlue(
            self.gorilla,
            **glue_context(),
            fields=['id', 'name'],
            form=TestModelForm,  # Pass class instead of instance
        ))

        policy = glue_object.policy
        children = glue_object._bound_children

        self.assertEqual(policy.children, {
            'form': f'{glue_object.address}.form',
        })
        self.assertEqual(children[0].glue_object.form['name'].value(), 'Koko')

    def test_model_forms_dict_can_contain_classes_instead_of_instances(self):
        """Verify that form classes can be passed in the forms dict."""
        glue_object = with_request(ModelGlue(
            self.gorilla,
            **glue_context(),
            fields=['id', 'name'],
            forms={'edit': TestModelForm},  # Pass class instead of instance
        ))

        policy = glue_object.policy
        self.assertNotIn('form', policy.children)
        self.assertEqual(
            policy.children['forms.edit'],
            f'{glue_object.address}.forms.edit',
        )

    def test_typed_glue_property_builds_addressed_child(self):
        glue_object = with_request(NestedDashboardGlue())

        policy = glue_object.policy
        children = glue_object._bound_children

        self.assertEqual(policy.children, {
            'stats': f'{glue_object.address}.stats',
        })
        self.assertNotIn('stats', policy.attributes)
        self.assertEqual(len(children), 1)
        child = children[0].glue_object
        self.assertEqual(child.namespace, 'stats')
        self.assertIn('score', child.policy.attributes)
        self.assertIn('reset', child.policy.attributes)

        context = AttributeCallRequestContext.model_construct(
            request=glue_object.request,
            target_glue_policy=policy,
            target_glue_updates={},
            target_attribute_name='stats',
            target_attribute_call_kwargs={},
        )
        with self.assertRaises(GlueCalledNonCallableAttributeError):
            glue_object.process_attribute_call(context)

    def test_declared_serializable_state_attribute_is_included(self):
        glue_object = with_request(DeclaredStateGlue())

        self.assertIn('count', glue_object.policy.attributes)
        self.assertEqual(glue_object.policy.state_snapshot['count'], 3)
        self.assertEqual(
            glue_object.get_static_data()['fields']['count'],
            {'value_path': 'count', 'editable': False},
        )

    def test_declared_nonserializable_value_without_nested_glue_attributes_raises(self):
        glue_object = with_request(InvalidServiceGlue())

        with self.assertRaises(GlueInvalidAttributeError) as context:
            glue_object._bound_attributes['service'].get()

        self.assertEqual(context.exception.attribute, 'service')
        self.assertIn('PlainService', context.exception.value_type)
        self.assertIn('Glue.attribute', str(context.exception))


class DjangoFormGlueObjectTestCase(TestCase):
    def test_form_foreign_key_choices_returns_configured_choices(self):
        from django import forms

        class SkillForm(forms.Form):
            name = forms.CharField()
            skill = forms.ModelChoiceField(queryset=Skill.objects.all())

        skill = Skill.objects.create(name='Grappling')
        glue_object = with_request(FormGlue(SkillForm(), **glue_context(name='skill-form')))
        context = AttributeCallRequestContext.model_construct(
            request=glue_object.request,
            target_glue_policy=glue_object.policy,
            target_glue_updates={
                'name': '',
                'skill': None,
            },
            target_attribute_name='foreign_key_choices',
            target_attribute_call_kwargs={'field_name': 'skill'},
        )

        payload, _introduced = glue_object.process_attribute_call(context)

        self.assertEqual(payload['result']['results'], [{
            'value': skill.pk,
            'label': 'Grappling',
            'obj': {'pk': skill.pk, '__str__': 'Grappling'},
        }])

    def test_unsearchable_foreign_key_choices_returns_every_row(self):
        from django import forms

        class SkillForm(forms.Form):
            skill = forms.ModelChoiceField(queryset=Skill.objects.all())

        for index in range(5):
            Skill.objects.create(name=f'Skill {index}')

        glue_object = FormGlue(SkillForm(), **glue_context(name='skill-form'))
        glue_object._load_client_state({'skill': None})

        result = glue_object.foreign_key_choices(field_name='skill')

        self.assertEqual(len(result['results']), 5)

    def test_foreign_key_choices_uses_model_choice_to_field_name(self):
        from django import forms

        class SkillForm(forms.Form):
            skill = forms.ModelChoiceField(
                queryset=Skill.objects.all(),
                to_field_name='name',
            )

        skill = Skill.objects.create(name='Grappling')
        glue_object = FormGlue(
            SkillForm(),
            **glue_context(name='skill-form'),
        )

        result = glue_object.foreign_key_choices(field_name='skill')

        self.assertEqual(result['results'], [{
            'value': 'Grappling',
            'label': 'Grappling',
            'obj': {
                'pk': skill.pk,
                '__str__': 'Grappling',
            },
        }])

        glue_object._load_client_state({
            'skill': 'Grappling',
        })
        self.assertTrue(glue_object.save()['valid'])

    def test_searchable_foreign_key_choices_limit_unfiltered_and_searched_results(self):
        from django import forms

        class SkillForm(forms.Form):
            skill = forms.ModelChoiceField(queryset=Glue.choices(
                Skill.objects.all(),
                search_fields=['name'],
                search_limit=2,
            ))

        skills = [Skill.objects.create(name=f'Skill {index}') for index in range(3)]

        glue_object = FormGlue(SkillForm(), **glue_context(name='skill-form'))
        glue_object._load_client_state({'skill': None})

        unfiltered = glue_object.foreign_key_choices(field_name='skill')
        self.assertEqual(
            [choice['value'] for choice in unfiltered['results']],
            [skill.pk for skill in skills[:2]],
        )
        result = glue_object.foreign_key_choices(
            field_name='skill',
            search='skill',
        )

        self.assertEqual(
            [choice['value'] for choice in result['results']],
            [skill.pk for skill in skills[:2]],
        )

    def test_foreign_key_choices_search_field_filters_with_icontains(self):
        from django import forms

        class SkillForm(forms.Form):
            skill = forms.ModelChoiceField(queryset=Glue.choices(
                Skill.objects.all(),
                search_fields=['name'],
            ))

        Skill.objects.create(name='Grappling')
        striking = Skill.objects.create(name='Striking')
        Skill.objects.create(name='Wrestling')

        glue_object = FormGlue(SkillForm(), **glue_context(name='skill-form'))
        glue_object._load_client_state({'skill': None})

        result = glue_object.foreign_key_choices(
            field_name='skill',
            search='strik',
        )

        self.assertEqual(result['results'], [{
            'value': striking.pk,
            'label': 'Striking',
            'obj': {'pk': striking.pk, '__str__': 'Striking'},
        }])

    def test_foreign_key_choices_searches_multiple_declared_fields(self):
        from django import forms

        class SkillForm(forms.Form):
            skill = forms.ModelChoiceField(queryset=Glue.choices(
                Skill.objects.all(),
                search_fields=['name', 'description'],
            ))

        name_match = Skill.objects.create(name='Defence', description='')
        description_match = Skill.objects.create(name='Guard', description='Defence skill')
        Skill.objects.create(name='Striking', description='Offence')
        glue_object = FormGlue(SkillForm(), **glue_context(name='skill-form'))

        result = glue_object.foreign_key_choices(
            field_name='skill',
            search='defence',
        )

        self.assertEqual(
            [choice['value'] for choice in result['results']],
            [name_match.pk, description_match.pk],
        )

    def test_foreign_key_choices_search_without_search_field_is_ignored(self):
        from django import forms

        class SkillForm(forms.Form):
            skill = forms.ModelChoiceField(queryset=Skill.objects.all())

        Skill.objects.create(name='Grappling')
        Skill.objects.create(name='Striking')

        glue_object = FormGlue(SkillForm(), **glue_context(name='skill-form'))
        glue_object._load_client_state({'skill': None})

        # A search term with no search_field can't be applied (there's no
        # generic way to filter on a model's __str__ at the database layer),
        # so it's a no-op rather than an error -- the field returns
        # unfiltered, matching how a widget that never opted into search
        # behaves if it's ever accidentally passed one.
        result = glue_object.foreign_key_choices(field_name='skill', search='strik')

        self.assertEqual(len(result['results']), 2)

    def test_foreign_key_choices_uses_server_owned_shape(self):
        from django import forms

        class SkillForm(forms.Form):
            skill = forms.ModelChoiceField(queryset=Glue.choices(
                Skill.objects.all(),
                fields=['name', 'difficulty'],
            ))

        skill = Skill.objects.create(
            name='Grappling',
            difficulty=3,
        )
        glue_object = FormGlue(SkillForm(), **glue_context(name='skill-form'))

        result = glue_object.foreign_key_choices(field_name='skill')

        self.assertEqual(result['results'], [{
            'value': skill.pk,
            'label': 'Grappling',
            'obj': {
                'pk': skill.pk,
                '__str__': 'Grappling',
                'name': 'Grappling',
                'difficulty': 3,
            },
        }])

    def test_queryset_choice_options_survive_form_field_cloning(self):
        from django import forms

        configured_queryset = Glue.choices(
            Skill.objects.all(),
            search_fields=['name'],
            fields=['name'],
            search_limit=10,
        )

        class SkillForm(forms.Form):
            skill = forms.ModelChoiceField(queryset=configured_queryset)

        field_queryset = SkillForm().fields['skill'].queryset
        options = GlueRelatedModelChoices(field_queryset).explicit_options

        self.assertIsNotNone(options)
        self.assertEqual(options.search_fields, ('name',))
        self.assertEqual(options.fields, ('name',))
        self.assertEqual(options.search_limit, 10)

    def test_queryset_choice_options_survive_queryset_cloning(self):
        configured_queryset = Glue.choices(
            Skill.objects.all(),
            search_fields=['name'],
            fields=['description'],
            search_limit=10,
        )
        cloned_querysets = [
            configured_queryset.all(),
            configured_queryset.filter(name='Grappling'),
            configured_queryset.exclude(name='Striking'),
            configured_queryset.order_by('name'),
            configured_queryset.distinct(),
        ]

        for cloned_queryset in cloned_querysets:
            with self.subTest(query=str(cloned_queryset.query)):
                options = GlueRelatedModelChoices(cloned_queryset).explicit_options

                self.assertIsNotNone(options)
                self.assertEqual(options.search_fields, ('name',))
                self.assertEqual(options.fields, ('description',))
                self.assertEqual(options.search_limit, 10)

    def test_reconfiguring_choice_queryset_does_not_mutate_source_options(self):
        original_queryset = Glue.choices(
            Skill.objects.all(),
            fields=['name'],
            search_limit=10,
        )
        reconfigured_queryset = Glue.choices(
            original_queryset,
            fields=['description'],
            search_limit=20,
        )

        original_options = GlueRelatedModelChoices(original_queryset).explicit_options
        reconfigured_options = GlueRelatedModelChoices(
            reconfigured_queryset
        ).explicit_options

        self.assertIsNotNone(original_options)
        self.assertIsNotNone(reconfigured_options)
        self.assertEqual(original_options.fields, ('name',))
        self.assertEqual(original_options.search_limit, 10)
        self.assertEqual(reconfigured_options.fields, ('description',))
        self.assertEqual(reconfigured_options.search_limit, 20)

    def test_choice_queryset_fingerprint_is_stable_for_equivalent_querysets(self):
        queryset = Glue.choices(
            Skill.objects.filter(name='Visible'),
            search_fields=['name'],
            fields=['description'],
            search_limit=25,
        )

        self.assertEqual(
            GlueRelatedModelChoices(queryset).fingerprint(),
            GlueRelatedModelChoices(queryset.all()).fingerprint(),
        )

    def test_choice_queryset_fingerprint_includes_query(self):
        visible_queryset = Glue.choices(
            Skill.objects.filter(name='Visible'),
            fields=['name'],
        )
        hidden_queryset = Glue.choices(
            Skill.objects.filter(name='Hidden'),
            fields=['name'],
        )

        self.assertNotEqual(
            GlueRelatedModelChoices(visible_queryset).fingerprint(),
            GlueRelatedModelChoices(hidden_queryset).fingerprint(),
        )

    def test_choice_queryset_fingerprint_includes_options(self):
        name_queryset = Glue.choices(
            Skill.objects.all(),
            search_fields=['name'],
            fields=['name'],
        )
        description_queryset = Glue.choices(
            Skill.objects.all(),
            search_fields=['description'],
            fields=['description'],
        )

        self.assertNotEqual(
            GlueRelatedModelChoices(name_queryset).fingerprint(),
            GlueRelatedModelChoices(description_queryset).fingerprint(),
        )

    def test_choice_queryset_fingerprint_includes_search_limit(self):
        small_limit_queryset = Glue.choices(
            Skill.objects.all(),
            search_limit=25,
        )
        large_limit_queryset = Glue.choices(
            Skill.objects.all(),
            search_limit=100,
        )

        self.assertNotEqual(
            GlueRelatedModelChoices(small_limit_queryset).fingerprint(),
            GlueRelatedModelChoices(large_limit_queryset).fingerprint(),
        )

    def test_choice_queryset_fingerprint_includes_value_field(self):
        queryset = Skill.objects.all()

        pk_fingerprint = GlueRelatedModelChoices(queryset).fingerprint()
        name_fingerprint = GlueRelatedModelChoices(
            queryset,
            value_field_name='name',
        ).fingerprint()

        self.assertNotEqual(pk_fingerprint, name_fingerprint)

    def test_choice_queryset_rejects_invalid_configuration(self):
        for search_limit in (0, -1, True, '5', 2.5):
            with self.assertRaises(ValueError):
                Glue.choices(
                    Skill.objects.all(),
                    search_limit=search_limit,
                )

        with self.assertRaises(ValueError):
            Glue.choices(
                Skill.objects.all(),
                search_fields=['missing'],
            )

        with self.assertRaises(ValueError):
            Glue.choices(
                Skill.objects.all(),
                search_fields=['gorillas__name'],
            )

        with self.assertRaises(ValueError):
            Glue.choices(
                Skill.objects.all(),
                search_fields=['gorillas'],
            )

        with self.assertRaises(ValueError):
            Glue.choices(Skill.objects.all(), fields=['pk'])

        with self.assertRaises(ValueError):
            Glue.choices(Skill.objects.all(), fields=['delete'])

        with self.assertRaises(ValueError):
            Glue.choices(Skill.objects.all(), fields=['gorillas'])

        with self.assertRaises(ValueError):
            Glue.choices(Gorilla.objects.all(), fields=['signature'])

        with self.assertRaises(ValueError):
            Glue.choices(
                Skill.objects.all()[:10],
                search_fields=['name'],
            )

    def test_unsearchable_foreign_key_choices_accepts_sliced_queryset(self):
        from django import forms

        class SkillForm(forms.Form):
            skill = forms.ModelChoiceField(queryset=Skill.objects.all()[:10])

        glue_object = FormGlue(
            SkillForm(),
            **glue_context(name='skill-form'),
        )

        self.assertEqual(
            glue_object.foreign_key_choices(field_name='skill'),
            {'results': []},
        )

    def test_static_choices_source_remains_compatible_with_choice_field(self):
        from django import forms

        choices = Glue.choices([
            ('draft', 'Draft'),
            ('published', 'Published'),
        ])
        field = forms.ChoiceField(choices=choices)

        self.assertEqual(list(field.choices), choices)

    def test_static_choices_reject_queryset_specific_options(self):
        choices = [('draft', 'Draft')]

        for options in (
            {'search_fields': ['label']},
            {'fields': ['description']},
            {'search_limit': 10},
        ):
            with self.subTest(options=options), self.assertRaises(TypeError):
                Glue.choices(choices, **options)

    def test_choice_queryset_accepts_declared_annotations(self):
        from django import forms

        skill = Skill.objects.create(name='Grappling')
        configured_queryset = Glue.choices(
            Skill.objects.annotate(presentation_name=F('name')),
            search_fields=['presentation_name'],
            fields=['presentation_name'],
        )

        class SkillForm(forms.Form):
            selected_skill = forms.ModelChoiceField(queryset=configured_queryset)

        glue_object = FormGlue(
            SkillForm(),
            **glue_context(name='skill-form'),
        )
        result = glue_object.foreign_key_choices(
            field_name='selected_skill',
            search='grap',
        )

        self.assertEqual(
            result['results'][0]['obj']['presentation_name'],
            skill.name,
        )

    def test_choice_queryset_deduplicates_search_fields(self):
        configured_queryset = Glue.choices(
            Skill.objects.all(),
            search_fields=['name', 'description', 'name'],
        )

        options = GlueRelatedModelChoices(configured_queryset).explicit_options

        self.assertIsNotNone(options)
        self.assertEqual(options.search_fields, ('name', 'description'))

    def test_choice_queryset_deduplicates_choice_fields(self):
        configured_queryset = Glue.choices(
            Skill.objects.all(),
            fields=['name', 'description', 'name'],
        )

        options = GlueRelatedModelChoices(configured_queryset).explicit_options

        self.assertIsNotNone(options)
        self.assertEqual(options.fields, ('name', 'description'))

    def test_form_field_adapter_builds_metadata(self):
        form = ContactForm()
        glue_object = FormGlue(form, **glue_context(name='contact'))
        attribute = glue_object.attributes['name']

        self.assertEqual(attribute.definition.required_access, GlueAccess.CHANGE)
        schema = attribute.schema()
        self.assertEqual(schema['type'], 'CharField')
        self.assertEqual(schema['max_length'], 100)

    def test_relation_field_metadata_marks_searchable_choices(self):
        from django import forms

        class SkillForm(forms.Form):
            skill = forms.ModelChoiceField(queryset=Glue.choices(
                Skill.objects.all(),
                search_fields=['name'],
            ))

        glue_object = FormGlue(SkillForm(), **glue_context(name='skill-form'))
        schema = glue_object.attributes['skill'].schema()

        self.assertTrue(schema['choices_searchable'])
        self.assertNotIn('choices_batch_size', schema)

    def test_relation_field_metadata_is_not_searchable_by_default(self):
        from django import forms

        class SkillForm(forms.Form):
            skill = forms.ModelChoiceField(queryset=Skill.objects.all())

        glue_object = FormGlue(SkillForm(), **glue_context(name='skill-form'))
        schema = glue_object.attributes['skill'].schema()

        self.assertFalse(schema['choices_searchable'])
        self.assertNotIn('choices_batch_size', schema)

    def test_searchable_relation_field_metadata_seeds_the_current_selection(self):
        from django import forms

        class SkillForm(forms.Form):
            skill = forms.ModelChoiceField(queryset=Glue.choices(
                Skill.objects.all(),
                search_fields=['name'],
            ))

        Skill.objects.create(name='Grappling')
        selected = Skill.objects.create(name='Striking')

        glue_object = FormGlue(SkillForm(initial={'skill': selected.pk}), **glue_context(name='skill-form'))
        computed = glue_object.attributes['skill'].computed_data()

        self.assertEqual(computed['selected_choice'], {
            'value': selected.pk,
            'label': 'Striking',
            'obj': {'pk': selected.pk, '__str__': 'Striking'},
        })

    def test_selected_choice_metadata_uses_declared_shape(self):
        from django import forms

        class SkillForm(forms.Form):
            skill = forms.ModelChoiceField(queryset=Glue.choices(
                Skill.objects.all(),
                search_fields=['name'],
                fields=['name', 'difficulty'],
            ))

        selected = Skill.objects.create(name='Grappling', difficulty=3)
        glue_object = FormGlue(
            SkillForm(initial={'skill': selected.pk}),
            **glue_context(name='skill-form'),
        )

        selected_choice = glue_object.attributes['skill'].computed_data()['selected_choice']

        self.assertEqual(selected_choice['obj'], {
            'pk': selected.pk,
            '__str__': 'Grappling',
            'name': 'Grappling',
            'difficulty': 3,
        })

    def test_searchable_multiple_choice_metadata_seeds_all_selected_choices(self):
        from django import forms

        class SkillForm(forms.Form):
            skills = forms.ModelMultipleChoiceField(queryset=Glue.choices(
                Skill.objects.all(),
                search_fields=['name'],
                fields=['difficulty'],
            ))

        grappling = Skill.objects.create(name='Grappling', difficulty=3)
        striking = Skill.objects.create(name='Striking', difficulty=4)
        glue_object = FormGlue(
            SkillForm(initial={'skills': [striking.pk, grappling.pk]}),
            **glue_context(name='skill-form'),
        )

        selected_choices = glue_object.attributes['skills'].computed_data()['selected_choices']

        self.assertEqual(
            [choice['value'] for choice in selected_choices],
            [striking.pk, grappling.pk],
        )
        self.assertEqual(
            [choice['obj']['difficulty'] for choice in selected_choices],
            [4, 3],
        )

    def test_selected_choice_metadata_uses_model_choice_to_field_name(self):
        from django import forms

        class SkillForm(forms.Form):
            skill = forms.ModelChoiceField(
                queryset=Glue.choices(
                    Skill.objects.all(),
                    search_fields=['name'],
                ),
                to_field_name='name',
            )

        selected = Skill.objects.create(name='Grappling')
        glue_object = FormGlue(
            SkillForm(initial={'skill': 'Grappling'}),
            **glue_context(name='skill-form'),
        )

        selected_choice = glue_object.attributes['skill'].computed_data()['selected_choice']

        self.assertEqual(selected_choice, {
            'value': 'Grappling',
            'label': 'Grappling',
            'obj': {
                'pk': selected.pk,
                '__str__': 'Grappling',
            },
        })

    def test_searchable_relation_field_metadata_has_no_selection_when_field_is_empty(self):
        from django import forms

        class SkillForm(forms.Form):
            skill = forms.ModelChoiceField(
                queryset=Glue.choices(
                    Skill.objects.all(),
                    search_fields=['name'],
                ),
                required=False,
            )

        Skill.objects.create(name='Grappling')

        glue_object = FormGlue(SkillForm(), **glue_context(name='skill-form'))
        computed = glue_object.attributes['skill'].computed_data()

        self.assertNotIn('selected_choice', computed)

    def test_form_adapter_builds_policy_state_and_metadata(self):
        form = ContactForm(initial={'name': 'Ada'})
        glue_object = with_request(FormGlue(form, **glue_context(name='contact')))

        policy = glue_object.policy
        static_data = glue_object.get_static_data()

        self.assertEqual(policy.namespace, 'form')
        self.assertIn('validate', policy.attributes)
        self.assertIn('save', policy.attributes)
        self.assertEqual(policy.state_snapshot['name'], 'Ada')
        self.assertEqual(static_data['fields']['email']['type'], 'EmailField')

    def test_form_entry_serializes_model_multiple_choice_initial_values(self):
        skill = Skill.objects.create(name='Grappling')
        gorilla = Gorilla.objects.create(name='Koko')
        gorilla.skills.add(skill)

        from django import forms

        class SkillForm(forms.ModelForm):
            class Meta:
                model = Gorilla
                fields = ['skills']

        glue_object = with_request(FormGlue(
            SkillForm(instance=gorilla, initial={'skills': [skill]}),
            **glue_context(name='gorilla-form'),
        ))

        entry = json.loads(json.dumps(glue_object.entry.model_dump(), cls=GlueResponseJSONEncoder))

        self.assertEqual(
            policy_from_entry(entry).identity['initial']['skills'],
            [skill.pk],
        )

    def test_form_policy_signature_is_stable_regardless_of_m2m_queryset_order(self):
        """An unordered ManyToMany queryset can iterate in a different row order on

        two evaluations of the "same" relation, even though nothing about the data
        changed. If that order leaked into the policy identity, equivalent forms would
        produce different authorization targets. Build the identity from two inputs
        holding the same rows in reversed order and assert both normalize identically.
        """
        skill_a = Skill.objects.create(name='Grappling')
        skill_b = Skill.objects.create(name='Striking')
        gorilla = Gorilla.objects.create(name='Koko')
        gorilla.skills.add(skill_a, skill_b)

        from django import forms

        class SkillForm(forms.ModelForm):
            class Meta:
                model = Gorilla
                fields = ['skills']

        forward = with_request(FormGlue(
            SkillForm(instance=gorilla, initial={'skills': [skill_a, skill_b]}),
            **glue_context(name='gorilla-form'),
        ))
        reversed_order = with_request(FormGlue(
            SkillForm(instance=gorilla, initial={'skills': [skill_b, skill_a]}),
            **glue_context(name='gorilla-form'),
        ))

        self.assertEqual(forward.identity, reversed_order.identity)
        self.assertEqual(
            reversed_order.identity['initial']['skills'],
            [skill_a.pk, skill_b.pk],
        )

    def test_form_field_get_reduces_model_choice_initial_to_pk(self):
        """Form field values must not leak raw model instances/querysets.

        An unbound ModelForm's initial can hold model instances/querysets for
        Model(Multiple)ChoiceField (e.g. instance=obj populates initial from
        model_to_dict). Regression test for a rename that accidentally
        dropped the prepare_value() call in the form-field value path.
        """
        skill = Skill.objects.create(name='Grappling')
        gorilla = Gorilla.objects.create(name='Koko')
        gorilla.skills.add(skill)

        from django import forms

        class SkillForm(forms.ModelForm):
            class Meta:
                model = Gorilla
                fields = ['skills']

        glue_object = with_request(FormGlue(
            SkillForm(instance=gorilla),
            **glue_context(name='gorilla-form'),
        ))

        attribute = glue_object.attributes['skills']

        self.assertEqual(attribute.get(), [skill.pk])
        self.assertEqual(glue_object.state['skills']['value'], [skill.pk])

    def test_form_field_get_falls_back_to_field_initial(self):
        """A bound form-field attribute's get() must match Django's own
        BoundField.value() semantics: prefer form.initial, fall back to
        field.initial when the form-level initial dict has no entry for the
        field.

        A field declared directly on a form (not backed by a model column,
        e.g. an extra ModelForm field populated in __init__ via
        `self.fields[name].initial = ...` rather than `self.initial[name] =
        ...`) renders fine in a classically-rendered Django form because
        BoundField.value() -> Form.get_initial_for_field() has this same
        fallback. Without it here, such a field silently serializes as None
        to the client even though Django's own rendering would show it.
        """
        from django import forms

        class ExtraFieldForm(forms.Form):
            name = forms.CharField()

        form = ExtraFieldForm()
        form.fields['name'].initial = 'Set via field.initial'

        glue_object = FormGlue(form, **glue_context(name='extra-field-form'))
        attribute = glue_object.attributes['name']

        self.assertEqual(attribute.get(), 'Set via field.initial')

    def test_form_field_get_prefers_form_initial_over_field_initial(self):
        from django import forms

        class ExtraFieldForm(forms.Form):
            name = forms.CharField()

        form = ExtraFieldForm(initial={'name': 'Set via form.initial'})
        form.fields['name'].initial = 'Set via field.initial'

        glue_object = FormGlue(form, **glue_context(name='extra-field-form'))
        attribute = glue_object.attributes['name']

        self.assertEqual(attribute.get(), 'Set via form.initial')

    def test_form_adapter_reconstruction_preserves_initial_data(self):
        gorilla = Gorilla.objects.create(name='Instance Name', age=12)
        glue_object = with_request(FormGlue(
            TestModelForm(
                instance=gorilla,
                initial={'name': 'Initial Name', 'age': 7},
            ),
            **glue_context(name='gorilla-form'),
        ))

        resolved = FormGlue._reconstruct_from_policy(glue_object.policy)

        self.assertEqual(resolved.form.initial['name'], 'Initial Name')
        self.assertEqual(resolved.form.initial['age'], 7)

    def test_form_adapter_reconstruction_prefers_initial_over_instance_values(self):
        gorilla = Gorilla.objects.create(name='Instance Name', age=12)
        glue_object = with_request(FormGlue(
            TestModelForm(
                instance=gorilla,
                initial={'name': 'Initial Name', 'age': 7},
            ),
            **glue_context(name='gorilla-form'),
        ))

        resolved = FormGlue._reconstruct_from_policy(glue_object.policy)
        state = resolved.state

        self.assertEqual(state['name']['value'], 'Initial Name')
        self.assertEqual(state['age']['value'], 7)

    def test_form_adapter_reconstruction_of_unsaved_instance_preserves_fk_initial(self):
        """A form built for a never-saved instance (no target_pk, e.g. via
        QuerySetGlue.new()) must still have those foreign keys on
        self.instance after reconstruction -- not just in form.initial --
        so a form method that reads self.instance.<field> (the same way it
        would for an already-saved, bound instance) sees the same value the
        client is about to submit, instead of an empty instance.
        """
        red = Gorilla.objects.create(name='Red Corner')
        blue = Gorilla.objects.create(name='Blue Corner')

        unsaved_fight = Fight(red_corner=red, blue_corner=blue)
        glue_object = with_request(FormGlue(
            FightForm(instance=unsaved_fight),
            **glue_context(name='fight-form'),
        ))
        self.assertIsNone(glue_object.form.instance.pk)

        resolved = FormGlue._reconstruct_from_policy(glue_object.policy)

        self.assertIsNone(resolved.form.instance.pk)
        self.assertEqual(resolved.form.instance.red_corner_id, red.pk)
        self.assertEqual(resolved.form.instance.blue_corner_id, blue.pk)

    def test_form_adapter_reconstruction_of_unsaved_instance_with_no_initial_still_works(self):
        """A brand-new form with nothing pre-filled (no instance= at all when
        constructed, target_pk None, initial {}) must still reconstruct
        cleanly -- _unsaved_instance_from_initial({}) should just build a
        plain empty instance, not raise.

        Reuses the module-level FightForm import rather than a form class
        defined here -- _reconstruct_from_policy resolves the form class via
        getattr(import_module(cls.__module__), cls.__name__), which only
        ever finds classes that are true module-level attributes; a class
        defined inside this method body would never be found this way (it's
        local to the function's scope, not the module's), regardless of name.
        """
        glue_object = with_request(FormGlue(FightForm(), **glue_context(name='fight-form')))

        resolved = FormGlue._reconstruct_from_policy(glue_object.policy)

        self.assertIsNone(resolved.form.instance.pk)
        self.assertIsNone(resolved.form.instance.red_corner_id)


class DjangoQuerySetGlueObjectTestCase(TestCase):
    def test_queryset_attr_declared_on_custom_queryset_class_is_bound_to_that_queryset(self):
        Gorilla.objects.create(name='Koko', age=18)
        Gorilla.objects.create(name='Kimba', age=5)
        Gorilla.objects.create(name='Bobo', age=12)

        filtered = GorillaCountingQuerySet(model=Gorilla).filter(age__gte=10)
        glue_object = with_request(QuerySetGlue(
            filtered,
            **glue_context(name='gorillas', access=GlueAccess.VIEW),
            fields=['name'],
        ))
        context = AttributeCallRequestContext.model_construct(
            request=glue_object.request,
            target_glue_policy=glue_object.policy,
            target_glue_updates={},
            target_attribute_name='count_names_starting_with',
            target_attribute_call_kwargs={'letter': 'k'},
        )

        entry, _introduced = glue_object.process_attribute_call(context)
        result = entry['result']

        # Only Koko matches: Kimba is excluded by the age>=10 filter already
        # applied on `filtered` before it reached QuerySetGlue.
        self.assertEqual(result, 1)

    def test_queryset_adapter_excludes_globally_excluded_fields(self):
        glue_object = QuerySetGlue(
            Gorilla.objects.all(),
            **glue_context(name='gorillas', access=GlueAccess.VIEW),
            exclude=['id'],
        )

        self.assertNotIn('signature', glue_object.attributes)
        self.assertNotIn(
            'signature',
            glue_object.get_static_data().get('fields', {}),
        )

    def test_queryset_adapter_requires_fields_or_exclude(self):
        with self.assertRaisesRegex(ValueError, 'QuerySetGlue requires at least one of fields or exclude'):
            QuerySetGlue(
                Gorilla.objects.all(),
                **glue_context(name='gorillas', access=GlueAccess.VIEW),
            )

    def test_queryset_query_encoding_returns_string(self):
        queryset = Gorilla.objects.all()

        encoded = pickle_query(queryset)

        self.assertIsInstance(encoded, str)
        self.assertGreater(len(encoded), 0)

    def test_queryset_query_decoding_returns_queryset(self):
        queryset = Gorilla.objects.all()

        restored = QuerySetGlue._decode_queryset_query(pickle_query(queryset), GORILLA_PATH)

        self.assertIsInstance(restored, QuerySet)

    def test_queryset_query_roundtrip_preserves_results(self):
        gorilla = Gorilla.objects.create(name='Koko')
        queryset = Gorilla.objects.filter(pk=gorilla.pk)

        restored = QuerySetGlue._decode_queryset_query(pickle_query(queryset), GORILLA_PATH)

        self.assertEqual(
            list(restored.values_list('pk', flat=True)),
            list(queryset.values_list('pk', flat=True)),
        )

    def test_queryset_query_roundtrip_preserves_ordering(self):
        Gorilla.objects.create(name='Young', age=10)
        Gorilla.objects.create(name='Old', age=30)
        queryset = Gorilla.objects.order_by('-age')

        restored = QuerySetGlue._decode_queryset_query(pickle_query(queryset), GORILLA_PATH)

        self.assertEqual(
            list(restored.values_list('pk', flat=True)),
            list(queryset.values_list('pk', flat=True)),
        )

    def test_queryset_adapter_builds_queryset_policy(self):
        gorilla = Gorilla.objects.create(name='Koko')
        skill = Skill.objects.create(name='Grappling')
        gorilla.skills.add(skill)
        queryset = Gorilla.objects.filter(pk=gorilla.pk)
        glue_object = with_request(QuerySetGlue(
            queryset,
            **glue_context(name='gorillas', access=GlueAccess.VIEW),
            fields=['id', 'name', 'skills'],
        ))

        policy = glue_object.policy
        static_data = glue_object.get_static_data()
        resolved = QuerySetGlue._reconstruct_from_policy(policy)

        self.assertEqual(policy.namespace, 'querySet')
        self.assertNotIn('form_identities', policy.identity)
        self.assertIn('query_with_params', policy.attributes)
        self.assertNotIn('skills', static_data.get('fields', {}))
        self.assertEqual(list(resolved.queryset), [gorilla])

    def test_queryset_query_returns_child_model_proxy_payloads(self):
        gorilla = Gorilla.objects.create(name='Koko')
        queryset = Gorilla.objects.filter(pk=gorilla.pk)
        request = request_with_session()
        glue_object = QuerySetGlue(
            queryset,
            name='gorillas',
            access=GlueAccess.CHANGE,
            fields=['id', 'name'],
        )
        glue_object.request = request
        result = glue_object.query_with_params(filter={'name': 'Koko'})

        row = addressed_row_entries(glue_object, result)[0]
        row_policy = GluePolicy.from_token(row['policy_token'])
        self.assertEqual(row_policy.namespace, 'model')
        self.assertEqual(row_policy.name, f'gorillas.{gorilla.pk}')
        self.assertEqual(row_policy.state_snapshot['name'], 'Koko')
        self.assertEqual(row['static_data']['fields']['name']['type'], 'CharField')

    def test_queryset_query_rows_are_addressed_model_payloads(self):
        gorilla = Gorilla.objects.create(name='Koko')
        request = request_with_session()
        glue_object = QuerySetGlue(
            Gorilla.objects.filter(pk=gorilla.pk),
            name='gorillas',
            access=GlueAccess.VIEW,
            fields=['id', 'name'],
        )
        glue_object.request = request

        row = addressed_row_entries(glue_object, glue_object.query_with_params())[0]

        row_policy = GluePolicy.from_token(row['policy_token'])
        self.assertEqual(row_policy.namespace, 'model')
        self.assertEqual(row_policy.name, f'gorillas.{gorilla.pk}')
        self.assertEqual(row['computed_data']['name'], 'Koko')

    def test_queryset_with_computed_attributes_adds_attribute_to_child_payloads(self):
        gorilla = Gorilla.objects.create(name='Koko')
        queryset = Gorilla.objects.filter(pk=gorilla.pk)
        request = request_with_session()

        glue_object = QuerySetGlue(
            queryset,
            name='gorillas',
            access=GlueAccess.VIEW,
            fields=['id', 'name'],
            computed_attributes={'badge_data': gorilla_badge_data},
        )
        glue_object.request = request

        result = glue_object.query_with_params()

        row = addressed_row_entries(glue_object, result)[0]
        self.assertIn('badge_data', GluePolicy.from_token(row['policy_token']).attributes)
        self.assertIn('badge_data', row['static_data']['fields'])
        self.assertEqual(row['computed_data']['badge_data'], {'label': 'KOKO'})
        self.assertTrue(
            glue_object.policy.identity['computed_attributes']['badge_data']['path'].endswith(
                'test_objects.gorilla_badge_data'
            )
        )
        self.assertEqual(glue_object.policy.identity['computed_attributes']['badge_data']['kwargs'], {})

    def test_queryset_with_computed_attributes_supports_kwargs(self):
        gorilla = Gorilla.objects.create(name='Koko')
        queryset = Gorilla.objects.filter(pk=gorilla.pk)
        request = request_with_session()

        glue_object = QuerySetGlue(
            queryset,
            name='gorillas',
            access=GlueAccess.VIEW,
            fields=['id', 'name'],
            computed_attributes={
                'badge_data': (gorilla_badge_data_with_suffix, {'suffix': '!'}),
            },
        )
        glue_object.request = request

        result = glue_object.query_with_params()

        self.assertEqual(addressed_row_entries(glue_object, result)[0]['computed_data']['badge_data'], {'label': 'KOKO!'})
        self.assertEqual(
            glue_object.policy.identity['computed_attributes']['badge_data']['kwargs'],
            {'suffix': '!'},
        )

    def test_queryset_computed_attributes_survive_policy_reconstruction(self):
        gorilla = Gorilla.objects.create(name='Koko')
        glue_object = with_request(QuerySetGlue(
            Gorilla.objects.filter(pk=gorilla.pk),
            name='gorillas',
            access=GlueAccess.VIEW,
            fields=['id', 'name'],
            computed_attributes={'badge_data': gorilla_badge_data},
        ))

        resolved = QuerySetGlue._reconstruct_from_policy(glue_object.policy)
        resolved.request = glue_object.request
        result = resolved.query_with_params()

        self.assertEqual(addressed_row_entries(resolved, result)[0]['computed_data']['badge_data'], {'label': 'KOKO'})

    def test_queryset_with_computed_attributes_rejects_non_importable_callables(self):
        with self.assertRaisesRegex(ValueError, 'importable top-level callables'):
            QuerySetGlue(
                Gorilla.objects.all(),
                name='gorillas',
                access=GlueAccess.VIEW,
                fields=['id', 'name'],
                computed_attributes={'badge_data': lambda gorilla: gorilla.name},
            )

    def test_queryset_shortcut_accepts_computed_attributes(self):
        gorilla = Gorilla.objects.create(name='Koko')
        request = request_with_session()

        glue_object = Glue.queryset(
            target=Gorilla.objects.filter(pk=gorilla.pk),
            request=request,
            unique_name='gorillas',
            access=Glue.Access.VIEW,
            fields=['id', 'name'],
            computed_attributes={'badge_data': gorilla_badge_data},
        )

        entry_policy = policy_from_entry(glue_object.entry.model_dump())
        self.assertEqual(entry_policy.namespace, 'querySet')
        self.assertNotIn('badge_data', entry_policy.attributes)

        result = glue_object.query_with_params()
        row = addressed_row_entries(glue_object, result)[0]
        self.assertIn('badge_data', GluePolicy.from_token(row['policy_token']).attributes)

    def test_queryset_form_class_adds_nested_form_to_child_model_payloads(self):
        gorilla = Gorilla.objects.create(name='Koko')
        queryset = Gorilla.objects.filter(pk=gorilla.pk)
        request = request_with_session()
        glue_object = QuerySetGlue(
            queryset,
            name='gorillas',
            access=GlueAccess.CHANGE,
            fields=['id', 'name'],
            form=TestModelForm(),
        )
        glue_object.request = request
        result = glue_object.query_with_params()

        row = addressed_row_entries(glue_object, result)[0]
        row_policy = GluePolicy.from_token(row['policy_token'])
        self.assertEqual(
            row_policy.children['form'],
            f'{row_policy.address}.form',
        )
        self.assertNotIn('form', row_policy.attributes)

    def test_queryset_get_returns_the_row_glue_with_a_signed_row_policy(self):
        gorilla = Gorilla.objects.create(name='Koko')
        request = request_with_session()
        glue_object = QuerySetGlue(
            Gorilla.objects.all(),
            name='gorillas',
            access=GlueAccess.CHANGE,
            fields=['id', 'name'],
            form=TestModelForm(),
        )
        glue_object.request = request
        row = glue_object.get(pk=gorilla.pk)

        self.assertIsInstance(row, ModelGlue)
        self.assertFalse(row.is_bound)
        row.request = request
        row_policy = row.policy
        self.assertEqual(row_policy.namespace, 'model')
        self.assertEqual(row_policy.name, f'gorillas.{gorilla.pk}')
        self.assertEqual(row_policy.identity['target_pk'], gorilla.pk)
        self.assertEqual(
            row_policy.children['form'],
            f'{row_policy.address}.form',
        )
        self.assertEqual(row_policy.state_snapshot['name'], 'Koko')

    def test_queryset_policy_remains_unsliced_after_query_with_params(self):
        Gorilla.objects.create(name='Koko')
        Gorilla.objects.create(name='Ndume')
        request = request_with_session()
        glue_object = QuerySetGlue(
            Gorilla.objects.all(),
            name='gorillas',
            access=GlueAccess.CHANGE,
            fields=['id', 'name'],
        )
        glue_object.request = request
        original_policy = glue_object.policy

        # First query with slice - should not affect the original policy
        context = AttributeCallRequestContext.model_construct(
            request=request,
            target_glue_policy=original_policy,
            target_glue_updates={},
            target_attribute_name='query_with_params',
            target_attribute_call_kwargs={
                'order_by': 'name',
                'slice': {'start': 0, 'stop': 1},
            },
        )
        glue_object.process_attribute_call(context)

        # Reconstruct from original policy (not response) and query again
        resolved = QuerySetGlue._reconstruct_from_policy(original_policy)
        resolved.request = request

        result = resolved.query_with_params(
            filter={'name__icontains': 'du'},
            order_by='-name',
            slice={'start': 0, 'stop': 1},
        )

        self.assertEqual(len(result['items']), 1)
        self.assertEqual(
            GluePolicy.from_token(addressed_row_entries(resolved, result)[0]['policy_token']).state_snapshot['name'],
            'Ndume',
        )


class PythonAdaptersTestCase(TestCase):
    def test_function_adapter_builds_execute_policy(self):
        glue_object = with_request(FunctionGlue(
            'django_glue.tests.glue.test_objects.sample_function',
            **glue_context(name='sample', access=GlueAccess.VIEW),
        ))

        policy = glue_object.policy
        static_data = glue_object.get_static_data()

        self.assertEqual(policy.namespace, 'function')
        self.assertIn('execute', policy.attributes)
        self.assertEqual(static_data['params'][0]['name'], 'amount')


class GlueClassRegistryTestCase(TestCase):
    def test_registry_resolves_glue_object_class_by_policy_namespace(self):
        registry = GlueClassRegistry()
        registry.register_glue_class(ModelGlue)
        gorilla = Gorilla.objects.create(name='Koko')
        policy = with_request(ModelGlue(
            gorilla,
            **glue_context(access=GlueAccess.VIEW),
            fields=['name'],
        )).policy

        resolved_class = registry.get_glue_class(policy.namespace)

        self.assertIs(resolved_class, ModelGlue)


def sample_function(amount: int, tax: float = 0.0):
    return amount + tax


def gorilla_badge_data(gorilla: Gorilla) -> dict[str, str]:
    return {'label': gorilla.name.upper()}


def gorilla_badge_data_with_suffix(gorilla: Gorilla, suffix: str = '') -> dict[str, str]:
    return {'label': f'{gorilla.name.upper()}{suffix}'}


class IntroductionTestCase(TestCase):
    """Every introduced entry is a complete first snapshot; a queryset's rows
    answer its queries instead (state-model.md §10)."""

    def test_model_entry_carries_its_derived_output(self):
        gorilla = Gorilla.objects.create(name='Koko')
        glue_object = with_request(ModelGlue(gorilla, **glue_context(), fields=['name']))

        entry = glue_object.entry.model_dump()

        self.assertEqual(entry['computed_data']['id'], gorilla.pk)
        self.assertEqual(entry['computed_data']['fields']['name'], {'errors': []})

    def test_form_entry_carries_its_derived_output(self):
        form = ContactForm(initial={'name': 'Ada', 'email': 'ada@test.com'})
        glue_object = with_request(FormGlue(form, **glue_context(name='contact', access=GlueAccess.CHANGE)))

        entry = glue_object.entry.model_dump()

        self.assertIn('name', entry['computed_data']['fields'])

    def test_queryset_entry_carries_no_rows(self):
        Gorilla.objects.create(name='Koko')
        queryset = Gorilla.objects.all()
        glue_object = with_request(QuerySetGlue(queryset, **glue_context(name='gorillas'), fields=['name']))

        entry = glue_object.entry.model_dump()

        self.assertNotIn('items', entry['computed_data'])

    def test_queryset_query_with_params_returns_items_with_state(self):
        Gorilla.objects.create(name='Koko')
        queryset = Gorilla.objects.all()
        request = request_with_session()
        glue_object = QuerySetGlue(
            queryset,
            name='gorillas',
            access=GlueAccess.VIEW,
            fields=['name'],
        )
        glue_object.request = request

        result = glue_object.query_with_params()

        self.assertIn('items', result)
        self.assertEqual(len(result['items']), 1)
        item = addressed_row_entries(glue_object, result)[0]
        self.assertIn('computed_data', item)
        self.assertEqual(item['computed_data']['name'], 'Koko')


class CachedPropertyTestCase(TestCase):
    """Tests for cached_property behavior on Glue objects."""

    def test_model_attributes_are_cached(self):
        gorilla = Gorilla.objects.create(name='Koko')
        glue_object = ModelGlue(gorilla, **glue_context(), fields=['name'])

        attrs1 = glue_object.attributes
        attrs2 = glue_object.attributes

        self.assertIs(attrs1, attrs2)

    def test_model_identity_returns_consistent_values(self):
        gorilla = Gorilla.objects.create(name='Koko')
        glue_object = ModelGlue(gorilla, **glue_context(), fields=['name'])

        id1 = glue_object.identity
        id2 = glue_object.identity

        self.assertEqual(id1, id2)

    def test_form_attributes_are_cached(self):
        form = ContactForm()
        glue_object = FormGlue(form, **glue_context(name='contact', access=GlueAccess.CHANGE))

        attrs1 = glue_object.attributes
        attrs2 = glue_object.attributes

        self.assertIs(attrs1, attrs2)

    def test_queryset_attributes_are_cached(self):
        queryset = Gorilla.objects.all()
        glue_object = QuerySetGlue(queryset, **glue_context(name='gorillas'), fields=['name'])

        attrs1 = glue_object.attributes
        attrs2 = glue_object.attributes

        self.assertIs(attrs1, attrs2)


class RelationProjectionTestCase(TestCase):
    def setUp(self) -> None:
        self.red = Gorilla.objects.create(name='Red Koko')
        self.blue = Gorilla.objects.create(name='Blue Bobo')
        self.fight = Fight.objects.create(
            name='Championship',
            red_corner=self.red,
            blue_corner=self.blue,
        )

    def test_flat_foreign_key_is_a_raw_identity_value(self) -> None:
        glue_object = with_request(ModelGlue(
            self.fight,
            **glue_context(name='fight'),
            fields=['name', 'red_corner'],
        ))

        assert glue_object.policy.state_snapshot['red_corner'] == self.red.pk
        assert 'red_corner' not in glue_object.policy.children
        assert glue_object.attributes['red_corner'].schema()['type'] == 'ForeignKey'

    def test_flat_nullable_foreign_key_keeps_none_identity(self) -> None:
        glue_object = with_request(ModelGlue(
            self.fight,
            **glue_context(name='fight'),
            fields=['winner'],
        ))

        assert glue_object.state['winner']['value'] is None
        assert 'winner' not in glue_object.policy.children

    def test_foreign_key_choice_schema_uses_configured_queryset(self) -> None:
        choice_queryset = Glue.choices(
            Gorilla.objects.all(),
            search_fields=['name'],
        )
        glue_object = with_request(ModelGlue(
            self.fight,
            **glue_context(name='fight'),
            fields=['red_corner'],
            choices={'red_corner': choice_queryset},
        ))

        attribute = glue_object.attributes['red_corner']
        schema = attribute.schema()
        computed = attribute.computed_data()

        assert schema['choices'] == []
        assert schema['pk_field'] == 'id'
        assert schema['choice_model_path'] == 'test_project.gorilla.models.Gorilla'
        assert schema['choices_searchable']
        assert GlueRelatedModelChoices(choice_queryset).fingerprint() in computed[
            'choices_cache_key'
        ]

    def test_flat_many_to_many_is_raw_membership(self) -> None:
        grappling = Skill.objects.create(name='Grappling')
        climbing = Skill.objects.create(name='Climbing')
        self.red.skills.add(grappling, climbing)
        glue_object = with_request(ModelGlue(
            self.red,
            **glue_context(name='gorilla'),
            fields=['skills'],
        ))

        assert set(glue_object.policy.state_snapshot['skills']) == {
            grappling.pk,
            climbing.pk,
        }
        assert 'skills' not in glue_object.policy.children
        assert glue_object.attributes['skills'].schema()['type'] == 'ManyToManyField'

    def test_flat_reverse_relation_is_raw_membership(self) -> None:
        glue_object = with_request(ModelGlue(
            self.red,
            **glue_context(name='gorilla'),
            fields=['fights_as_red_corner'],
        ))

        assert glue_object.state['fights_as_red_corner']['value'] == (
            self.fight.pk,
        )
        assert 'fights_as_red_corner' not in glue_object.policy.children

    def test_all_fields_does_not_introduce_relation_children(self) -> None:
        from django_glue.glue.objects.django.model.object import ALL_FIELDS

        glue_object = with_request(ModelGlue(
            self.red,
            **glue_context(name='gorilla'),
            fields=ALL_FIELDS,
        ))

        assert glue_object.attributes['skills'].schema()['type'] == 'ManyToManyField'
        assert 'skills' not in glue_object.policy.children
        assert 'fights_as_red_corner' not in glue_object.attributes
        assert glue_object.policy.children == {}

    def test_many_to_many_is_an_editable_identity_value(self) -> None:
        from django_glue.glue.objects.django.model.object import ALL_FIELDS

        chest_pound = Skill.objects.create(name='Chest Pound')
        self.red.skills.set([chest_pound])
        glue_object = with_request(ModelGlue(
            self.red,
            **glue_context(name='gorilla'),
            fields=ALL_FIELDS,
        ))

        assert glue_object.state['skills']['value'] == (chest_pound.pk,)
        assert 'skills' in glue_object.editable
        schema = glue_object.attributes['skills'].schema()
        assert schema['choice_model_path'].endswith('.Skill')
        assert 'choice_model_path' in schema
