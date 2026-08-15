from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import cached_property
from types import SimpleNamespace

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import QuerySet
from django.test import TestCase

from django_glue import Glue
from django_glue.access import GlueAccess
from django_glue.glue import (
    BaseGlue,
    FormFieldAttribute,
    ModelFieldAttribute,
    FormGlue,
    ModelGlue,
    QuerySetGlue,
    TemplateGlue,
    GluePolicy,
    FunctionGlue,
    JsonGlue,
    CollectionGlue,
    GlueClassRegistry,
)
from django_glue.glue.loading import LoadingStrategy
from django_glue.glue.attributes import DeclaredAttribute, CompositeStateAttribute, GlueObjectAttribute
from django_glue.encoders import GlueResponseJSONEncoder
from django_glue.exceptions import (
    GlueCalledStateAttributeError,
    GlueInvalidAttributeError,
    GlueInvalidPolicyError,
)
from django_glue.response import GlueResponse
from django_glue.resolver.attribute_call.context import AttributeCallRequestContext
from test_project.gorilla.models import Gorilla, Skill
from test_project.fight.models import Fight
from test_project.test_forms import ContactForm, TestModelForm


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

    @DeclaredAttribute(access=GlueAccess.VIEW)
    def score(self) -> int:
        return 42

    @DeclaredAttribute(access=GlueAccess.CHANGE)
    def reset(self) -> str:
        return 'reset'


class NestedDashboardGlue(BaseGlue):
    namespace = 'dashboard'
    stats = DeclaredAttribute(NestedStatsGlue(), access=GlueAccess.VIEW)

    def __init__(self):
        super().__init__(name='dashboard', access=GlueAccess.CHANGE)

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
    day_collection = DeclaredAttribute(
        CollectionGlue([NestedStatsGlue()], name='internal_days'),
        access=GlueAccess.VIEW,
    )

    def __init__(self):
        super().__init__(name='collectionDashboard', access=GlueAccess.VIEW)

    @classmethod
    def _reconstruct_from_policy(cls, policy):
        return cls()


class DescriptorDefaultGlue(BaseGlue):
    namespace = 'descriptorDefault'
    count = DeclaredAttribute(0, access=GlueAccess.VIEW)
    values = DeclaredAttribute(access=GlueAccess.VIEW, default_factory=list)

    def __init__(self):
        super().__init__(name='descriptorDefault', access=GlueAccess.VIEW)

    @classmethod
    def _reconstruct_from_policy(cls, policy):
        return cls()


class PlainService:
    pass


class DeclaredStateGlue(BaseGlue):
    namespace = 'declared_state'
    count = DeclaredAttribute(3, access=GlueAccess.VIEW)

    def __init__(self):
        super().__init__(name='declared_state', access=GlueAccess.CHANGE)

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


class InvalidServiceGlue(DeclaredStateGlue):
    service = DeclaredAttribute(PlainService(), access=GlueAccess.DELETE)


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

    def test_model_all_fields_includes_all_model_fields(self):
        from django_glue.glue.objects.django.model.object import ALL_FIELDS

        glue_object = ModelGlue(
            self.gorilla,
            **glue_context(access=GlueAccess.VIEW),
            fields=ALL_FIELDS,
        )

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

        metadata = glue_object.metadata
        self.assertIn('name', metadata['attributes'])
        self.assertIn('age', metadata['attributes'])
        self.assertNotIn('signature', metadata['attributes'])

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
        row = result['items'][0]
        self.assertEqual(row['state']['name']['value'], 'Koko')
        self.assertNotIn('signature', row['state'])

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

        row = result['items'][0]
        self.assertIn('red_corner_id', row['state'])
        self.assertNotIn('red_corner', row['state'])

    def test_queryset_all_fields_includes_select_related_forward_relations(self):
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
        self.assertIn('red_corner', glue_object._included_fields)
        self.assertIn('blue_corner_id', glue_object._included_fields)
        self.assertNotIn('blue_corner', glue_object._included_fields)

        result = glue_object.query_with_params()

        row = result['items'][0]
        self.assertIn('red_corner_id', row['state'])
        self.assertIn('red_corner', row['state'])
        self.assertIn('name', row['state']['red_corner'])
        self.assertEqual(row['state']['red_corner']['name']['value'], 'Red Koko')
        self.assertIn('blue_corner_id', row['state'])
        self.assertNotIn('blue_corner', row['state'])


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

    def test_declared_glue_object_default_is_copied_per_instance(self):
        first = CollectionDashboardGlue()
        second = CollectionDashboardGlue()

        first.day_collection.items.append(DeclaredStateGlue())

        self.assertIsNot(first.day_collection, second.day_collection)
        self.assertIsNot(first.day_collection.items[0], second.day_collection.items[0])
        self.assertEqual(len(first.day_collection.items), 2)
        self.assertEqual(len(second.day_collection.items), 1)

    def test_state_reads_nested_glue_attribute_state_once(self):
        glue_object = with_request(NestedDashboardGlue())
        original_state = GlueObjectAttribute.state.fget
        call_count = 0

        def counted_state(attribute):
            nonlocal call_count
            call_count += 1
            return original_state(attribute)

        GlueObjectAttribute.state = property(counted_state)
        try:
            glue_object.state
        finally:
            GlueObjectAttribute.state = property(original_state)

        self.assertEqual(call_count, 1)

    def test_nested_glue_object_name_comes_from_attribute_path(self):
        glue_object = with_request(CollectionDashboardGlue())

        nested_policy = next(
            attribute
            for attribute in glue_object.policy.attributes
            if hasattr(attribute, 'namespace') and attribute.namespace == 'collection'
        )

        self.assertIn('day_collection', glue_object.state)
        self.assertNotIn('internal_days', glue_object.state)
        self.assertEqual(nested_policy.name, 'collectionDashboard.day_collection')
        self.assertEqual(nested_policy.attributes[0].name, 'collectionDashboard.day_collection.items.0')

    def test_collection_policy_contains_ordered_item_refs(self):
        glue_object = with_request(CollectionGlue(
            [
                NestedStatsGlue(),
                DeclaredStateGlue(),
            ],
            name='dashboard_items',
            access=GlueAccess.VIEW,
        ))

        policy = glue_object.policy

        self.assertEqual(policy.namespace, 'collection')
        self.assertEqual(policy.identity, {})
        self.assertEqual([
            attribute.namespace
            for attribute in policy.attributes
        ], ['stats', 'declared_state'])
        self.assertEqual([
            attribute.name
            for attribute in policy.attributes
        ], ['dashboard_items.items.0', 'dashboard_items.items.1'])
        self.assertEqual(glue_object.state['items.0'], {})
        self.assertEqual(glue_object.state['items.1']['count']['value'], 3)

    def test_collection_shortcut_registers_collection_only(self):
        request = request_with_session()

        collection = Glue.collection(request, 'dashboard_items', [
            NestedStatsGlue(),
            DeclaredStateGlue(),
        ])

        manifests = request.__dict__['__glue_manifest__']

        self.assertIsInstance(collection, CollectionGlue)
        self.assertEqual([manifest.name for manifest in manifests], ['dashboard_items'])
        self.assertEqual([
            attribute.name
            for attribute in collection.policy.attributes
        ], ['dashboard_items.items.0', 'dashboard_items.items.1'])

    def test_response_serializes_returned_glue_objects(self):
        glue_object = with_request(NestedDashboardGlue())
        collection = CollectionGlue(
            [NestedStatsGlue()],
            name='dashboard_items',
            access=GlueAccess.VIEW,
        )

        response = GlueResponse.from_result({
            'day_collection': collection,
        }).to_payload()
        serialized = GlueResponse._serialize_glue_values(response, glue_object)

        payload = serialized['result']['day_collection']
        self.assertEqual(payload['policy']['namespace'], 'collection')
        self.assertEqual(payload['policy']['name'], 'dashboard_items')
        self.assertIn('state', payload)

    def test_signed_policy_validates_without_preserving_proxy_policy_shape(self):
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
        restored = GluePolicy.model_validate(payload)

        self.assertEqual(restored.namespace, 'model')
        self.assertIn('identity', payload)
        self.assertIn('attributes', payload)
        self.assertNotIn('subject_details', payload)
        self.assertNotIn('bound_attributes', payload)

    def test_signed_policy_with_datetime_validates_after_json_transport(self):
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

        payload = json.loads(json.dumps(policy.model_dump(), cls=GlueResponseJSONEncoder))
        restored = GluePolicy.model_validate(payload)

        self.assertEqual(restored.identity['initial']['sent_datetime'], '2026-08-14T12:30:00Z')

    def test_signed_policy_rejects_tampering(self):
        policy = GluePolicy.new_signed_policy({
            'session_id': 'test-session',
            'request_user_id': None,
            'name': 'gorilla',
            'namespace': 'model',
            'identity': {'target_pk': 1},
            'access': GlueAccess.VIEW,
            'attributes': [],
        })
        payload = policy.model_dump()
        payload['identity']['target_pk'] = 2

        with self.assertRaises(GlueInvalidPolicyError):
            GluePolicy.model_validate(payload)


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

        self.assertEqual(attribute.required_access, GlueAccess.VIEW)
        self.assertEqual(attribute.metadata['type'], 'DateTimeField')
        self.assertFalse(attribute.metadata['editable'])

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
            glue_object.metadata['attributes'],
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
        state = glue_object.state
        metadata = glue_object.metadata

        self.assertEqual(policy.namespace, 'model')
        self.assertEqual(policy.identity['target_pk'], self.gorilla.pk)
        self.assertIn('save', policy.attributes)
        self.assertIn('delete', policy.attributes)
        self.assertEqual(state['name']['value'], 'Koko')
        self.assertEqual(metadata['attributes']['name']['type'], 'CharField')
        self.assertFalse(metadata['attributes']['name']['disabled'])
        self.assertEqual(metadata['attributes']['created_at']['type'], 'DateTimeField')
        self.assertTrue(metadata['attributes']['created_at']['disabled'])

    def test_model_relation_field_metadata_has_stable_choice_shape(self):
        glue_object = ModelGlue(self.gorilla, **glue_context(), fields=['skills'])

        metadata = glue_object.metadata
        skills_metadata = metadata['attributes']['skills']

        # M2M fields are now exposed as nested QuerySetGlue proxies
        self.assertEqual(skills_metadata['type'], 'ManyToManyField')
        self.assertEqual(skills_metadata['namespace'], 'related_set')
        self.assertEqual(skills_metadata['relation_type'], 'm2m')
        self.assertEqual(skills_metadata['related_model'], 'test_project.gorilla.models.Skill')
        self.assertIn('lazy', skills_metadata)
        self.assertIn('glue_namespace', skills_metadata)
        self.assertEqual(skills_metadata['glue_namespace'], 'querySet')

    def test_model_foreign_key_choices_returns_related_choices(self):
        skill = Skill.objects.create(name='Grappling')
        glue_object = ModelGlue(self.gorilla, **glue_context(), fields=['skills'])

        result = glue_object.foreign_key_choices(field_name='skills', choice_fields=['name'])

        self.assertEqual(result, [{
            'value': skill.pk,
            'label': 'Grappling',
            'obj': {'pk': skill.pk, '__str__': 'Grappling', 'name': 'Grappling'},
        }])

    def test_model_save_normalizes_rich_relation_and_file_state(self):
        skill = Skill.objects.create(name='Grappling')
        glue_object = with_request(ModelGlue(
            self.gorilla,
            **glue_context(),
            fields=['name', 'age', 'weight', 'height', 'profile_photo', 'skills'],
        ))

        # Load state before save (normally done during object resolution)
        glue_object._load_client_state({
            'name': {'value': 'Ndume'},
            'age': {'value': 22},
            'weight': {'value': 162.2},
            'height': {'value': 1.5},
            'profile_photo': {'value': {'name': 'existing.png', 'url': '/media/existing.png'}},
            'skills': {'value': [skill.pk]},
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

        # Load state before save (normally done during object resolution)
        glue_object._load_client_state({
            'name': {'value': self.gorilla.name},
            'age': {'value': self.gorilla.age},
            'weight': {'value': self.gorilla.weight},
            'height': {'value': self.gorilla.height},
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
        metadata = glue_object.metadata
        state = glue_object.state

        self.assertIn('badge_data', policy.attributes)
        self.assertEqual(metadata['attributes']['badge_data']['namespace'], 'readonly')
        self.assertEqual(state['badge_data']['value'], {'label': 'KOKO'})
        self.assertTrue(
            policy.identity['computed_attributes']['badge_data']['path'].endswith(
                'test_adapters.gorilla_badge_data'
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
            request,
            'gorilla',
            self.gorilla,
            Glue.Access.VIEW,
            fields=['id', 'name'],
            computed_attributes={'badge_data': gorilla_badge_data},
        )

        manifest = glue_object.manifest.model_dump()

        self.assertEqual(manifest['policy']['namespace'], 'model')
        self.assertIn('badge_data', manifest['policy']['attributes'])

    def test_model_adapter_transfers_target_glue_attributes_to_policy(self):
        glue_object = with_request(ModelGlue(self.gorilla, **glue_context(), fields=['id', 'name']))
        policy = glue_object.policy
        metadata = glue_object.metadata
        state = glue_object.state

        self.assertIn('shout', policy.attributes)
        self.assertIn('services.increment_age', policy.attributes)
        self.assertEqual(metadata['attributes']['services']['namespace'], 'composite')
        self.assertEqual(
            metadata['attributes']['services.increment_age']['namespace'],
            'callable',
        )
        self.assertIn('services', state)

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
        metadata = glue_object.metadata
        state = glue_object.state

        # 'form' is an alias for 'forms.default', both map to same nested policy
        self.assertTrue(policy_has_attribute(policy, 'form'))
        self.assertTrue(policy_has_attribute(policy, 'forms.default'))
        self.assertIsInstance(glue_object.attributes['form'], GlueObjectAttribute)
        self.assertIs(glue_object.attributes['form'], glue_object.attributes['forms.default'])
        self.assertEqual(metadata['attributes']['form']['namespace'], 'glue')
        self.assertEqual(metadata['attributes']['form']['glue_namespace'], 'form')
        self.assertEqual(state['form']['name']['value'], 'Koko')
        self.assertEqual(state['forms.default']['name']['value'], 'Koko')

    def test_model_form_classes_exposes_named_forms(self):
        glue_object = with_request(ModelGlue(
            self.gorilla,
            **glue_context(),
            fields=['id', 'name'],
            forms={'edit': TestModelForm(instance=self.gorilla)},
        ))

        policy = glue_object.policy
        metadata = glue_object.metadata

        self.assertFalse(policy_has_attribute(policy, 'form'))
        self.assertTrue(policy_has_attribute(policy, 'forms.edit'))
        self.assertEqual(metadata['attributes']['forms.edit']['namespace'], 'glue')
        self.assertEqual(metadata['attributes']['forms.edit']['glue_namespace'], 'form')

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
        metadata = glue_object.metadata
        state = glue_object.state

        # Should work the same as passing an instance
        self.assertTrue(policy_has_attribute(policy, 'form'))
        self.assertTrue(policy_has_attribute(policy, 'forms.default'))
        self.assertEqual(metadata['attributes']['form']['namespace'], 'glue')
        self.assertEqual(metadata['attributes']['form']['glue_namespace'], 'form')
        # State should have form field data from the model instance
        self.assertEqual(state['form']['name']['value'], 'Koko')

    def test_model_forms_dict_can_contain_classes_instead_of_instances(self):
        """Verify that form classes can be passed in the forms dict."""
        glue_object = with_request(ModelGlue(
            self.gorilla,
            **glue_context(),
            fields=['id', 'name'],
            forms={'edit': TestModelForm},  # Pass class instead of instance
        ))

        policy = glue_object.policy
        metadata = glue_object.metadata

        self.assertFalse(policy_has_attribute(policy, 'form'))
        self.assertTrue(policy_has_attribute(policy, 'forms.edit'))
        self.assertEqual(metadata['attributes']['forms.edit']['namespace'], 'glue')
        self.assertEqual(metadata['attributes']['forms.edit']['glue_namespace'], 'form')

    def test_nested_base_glue_attributes_build_composite_metadata(self):
        glue_object = with_request(NestedDashboardGlue())

        policy = glue_object.policy
        metadata = glue_object.metadata
        state = glue_object.state

        # Find the nested policy (not a string attribute like 'load_state')
        nested_policy = next(attr for attr in policy.attributes if hasattr(attr, 'name'))
        self.assertEqual(nested_policy.name, 'dashboard.stats')
        self.assertEqual(nested_policy.namespace, 'stats')
        self.assertIn('score', nested_policy.attributes)
        self.assertIn('reset', nested_policy.attributes)
        self.assertEqual(metadata['attributes']['stats']['namespace'], 'glue')
        self.assertEqual(metadata['attributes']['stats']['glue_namespace'], 'stats')
        self.assertEqual(metadata['attributes']['stats']['metadata']['attributes']['score']['namespace'], 'callable')
        self.assertEqual(metadata['attributes']['stats']['metadata']['attributes']['reset']['namespace'], 'callable')
        self.assertIn('stats', state)

        context = AttributeCallRequestContext.model_construct(
            request=glue_object.request,
            target_glue_policy=policy,
            target_glue_client_state=None,
            target_attribute_name='stats',
            target_attribute_call_kwargs={},
        )
        with self.assertRaises(GlueCalledStateAttributeError):
            glue_object.process_attribute_call(context)

    def test_declared_serializable_state_attribute_is_included(self):
        glue_object = with_request(DeclaredStateGlue())

        self.assertIn('count', glue_object.policy.attributes)
        self.assertEqual(glue_object.state['count']['value'], 3)
        self.assertEqual(glue_object.metadata['attributes']['count']['namespace'], 'readonly')

    def test_declared_nonserializable_value_without_nested_glue_attributes_raises(self):
        glue_object = with_request(InvalidServiceGlue())

        with self.assertRaises(GlueInvalidAttributeError) as context:
            _ = glue_object.policy

        self.assertEqual(context.exception.attribute, 'service')
        self.assertIn('PlainService', context.exception.value_type)
        self.assertIn('Glue.attribute', str(context.exception))


class DjangoFormGlueObjectTestCase(TestCase):
    def test_foreign_key_choices_does_not_return_validated_form_state(self):
        from django import forms

        class SkillForm(forms.Form):
            name = forms.CharField()
            skill = forms.ModelChoiceField(queryset=Skill.objects.all())

        skill = Skill.objects.create(name='Grappling')
        glue_object = with_request(FormGlue(SkillForm(), **glue_context(name='skill-form')))
        context = AttributeCallRequestContext.model_construct(
            request=glue_object.request,
            target_glue_policy=glue_object.policy,
            target_glue_client_state={
                'name': {'value': ''},
                'skill': {'value': None},
            },
            target_attribute_name='foreign_key_choices',
            target_attribute_call_kwargs={'field_name': 'skill'},
        )
        glue_object._load_client_state(context.target_glue_client_state)

        response = glue_object.process_attribute_call(context)
        payload = json.loads(response.content)

        self.assertEqual(payload['result'], [{
            'value': skill.pk,
            'label': 'Grappling',
            'obj': {'pk': skill.pk, '__str__': 'Grappling'},
        }])
        self.assertNotIn('state', payload)
        self.assertNotIn('policy', payload)
        self.assertNotIn('metadata', payload)

    def test_form_field_adapter_builds_metadata(self):
        form = ContactForm()
        glue_object = FormGlue(form, **glue_context(name='contact'))
        attribute = glue_object.attributes['name']

        self.assertEqual(attribute.required_access, GlueAccess.CHANGE)
        self.assertEqual(attribute.metadata['type'], 'CharField')
        self.assertEqual(attribute.metadata['max_length'], 100)

    def test_form_adapter_builds_policy_state_and_metadata(self):
        form = ContactForm(initial={'name': 'Ada'})
        glue_object = with_request(FormGlue(form, **glue_context(name='contact')))

        policy = glue_object.policy
        state = glue_object.state
        metadata = glue_object.metadata

        self.assertEqual(policy.namespace, 'form')
        self.assertIn('validate', policy.attributes)
        self.assertIn('save', policy.attributes)
        self.assertEqual(state['name']['value'], 'Ada')
        self.assertEqual(metadata['attributes']['email']['type'], 'EmailField')

    def test_form_manifest_serializes_model_multiple_choice_initial_values(self):
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

        manifest = json.loads(json.dumps(glue_object.manifest.model_dump(), cls=GlueResponseJSONEncoder))

        self.assertEqual(manifest['policy']['identity']['initial']['skills'], [skill.pk])

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
        state = resolved.load_state()

        self.assertEqual(state['name']['value'], 'Initial Name')
        self.assertEqual(state['age']['value'], 7)


class DjangoQuerySetGlueObjectTestCase(TestCase):
    def test_queryset_adapter_excludes_globally_excluded_fields(self):
        glue_object = QuerySetGlue(
            Gorilla.objects.all(),
            **glue_context(name='gorillas', access=GlueAccess.VIEW),
            exclude=['id'],
        )

        self.assertNotIn('signature', glue_object.attributes)
        self.assertNotIn(
            'signature',
            glue_object.metadata['attributes'],
        )

    def test_queryset_adapter_requires_fields_or_exclude(self):
        with self.assertRaisesRegex(ValueError, 'QuerySetGlue requires at least one of fields or exclude'):
            QuerySetGlue(
                Gorilla.objects.all(),
                **glue_context(name='gorillas', access=GlueAccess.VIEW),
            )

    def test_queryset_query_encoding_returns_string(self):
        queryset = Gorilla.objects.all()

        encoded = QuerySetGlue._encode_queryset_query(queryset)

        self.assertIsInstance(encoded, str)
        self.assertGreater(len(encoded), 0)

    def test_queryset_query_decoding_returns_queryset(self):
        queryset = Gorilla.objects.all()

        restored = QuerySetGlue._decode_queryset_query(
            QuerySetGlue._encode_queryset_query(queryset)
        )

        self.assertIsInstance(restored, QuerySet)

    def test_queryset_query_roundtrip_preserves_results(self):
        gorilla = Gorilla.objects.create(name='Koko')
        queryset = Gorilla.objects.filter(pk=gorilla.pk)

        restored = QuerySetGlue._decode_queryset_query(
            QuerySetGlue._encode_queryset_query(queryset)
        )

        self.assertEqual(
            list(restored.values_list('pk', flat=True)),
            list(queryset.values_list('pk', flat=True)),
        )

    def test_queryset_query_roundtrip_preserves_ordering(self):
        Gorilla.objects.create(name='Young', age=10)
        Gorilla.objects.create(name='Old', age=30)
        queryset = Gorilla.objects.order_by('-age')

        restored = QuerySetGlue._decode_queryset_query(
            QuerySetGlue._encode_queryset_query(queryset)
        )

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
        metadata = glue_object.metadata
        resolved = QuerySetGlue._reconstruct_from_policy(policy)

        self.assertEqual(policy.namespace, 'querySet')
        self.assertNotIn('form_identities', policy.identity)
        self.assertIn('query_with_params', policy.attributes)
        self.assertEqual(metadata['attributes']['skills']['type'], 'ManyToManyField')
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
        policy = glue_object.policy

        result = glue_object.query_with_params(filter={'name': 'Koko'})

        row = result['items'][0]
        self.assertEqual(row['policy']['namespace'], 'model')
        self.assertEqual(row['policy']['name'], f'gorillas.{gorilla.pk}')
        self.assertEqual(row['state']['name']['value'], 'Koko')
        self.assertEqual(row['metadata']['attributes']['name']['type'], 'CharField')

    def test_queryset_eager_state_contains_child_model_proxy_payloads(self):
        gorilla = Gorilla.objects.create(name='Koko')
        request = request_with_session()
        glue_object = QuerySetGlue(
            Gorilla.objects.filter(pk=gorilla.pk),
            name='gorillas',
            access=GlueAccess.VIEW,
            fields=['id', 'name'],
            loading_strategy=LoadingStrategy.EAGER,
        )
        glue_object.request = request

        manifest = glue_object.manifest.model_dump()
        state = manifest['state']
        row = state['items'][0]

        self.assertEqual(manifest['loading_strategy'], 'eager')
        self.assertEqual(row['policy']['namespace'], 'model')
        self.assertEqual(row['policy']['name'], f'gorillas.{gorilla.pk}')
        self.assertEqual(row['state']['name']['value'], 'Koko')

    def test_queryset_loading_strategy_not_in_policy_identity(self):
        glue_object = with_request(QuerySetGlue(
            Gorilla.objects.all(),
            name='gorillas',
            access=GlueAccess.VIEW,
            fields=['id', 'name'],
            loading_strategy=LoadingStrategy.EAGER,
        ))

        # loading_strategy should NOT be in policy identity - it's transport behavior, not capability
        self.assertNotIn('eager', glue_object.policy.identity)
        self.assertNotIn('loading_strategy', glue_object.policy.identity)
        # But it should be in the manifest
        self.assertEqual(glue_object.manifest.loading_strategy, LoadingStrategy.EAGER)

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

        row = result['items'][0]
        self.assertIn('badge_data', row['policy']['attributes'])
        self.assertEqual(row['metadata']['attributes']['badge_data']['namespace'], 'readonly')
        self.assertEqual(row['state']['badge_data']['value'], {'label': 'KOKO'})
        self.assertTrue(
            glue_object.policy.identity['computed_attributes']['badge_data']['path'].endswith(
                'test_adapters.gorilla_badge_data'
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

        self.assertEqual(result['items'][0]['state']['badge_data']['value'], {'label': 'KOKO!'})
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

        self.assertEqual(result['items'][0]['state']['badge_data']['value'], {'label': 'KOKO'})

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
            request,
            'gorillas',
            Gorilla.objects.filter(pk=gorilla.pk),
            Glue.Access.VIEW,
            fields=['id', 'name'],
            computed_attributes={'badge_data': gorilla_badge_data},
        )

        manifest = glue_object.manifest.model_dump()

        self.assertEqual(manifest['policy']['namespace'], 'querySet')
        self.assertIn('badge_data', manifest['policy']['attributes'])

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
        policy = glue_object.policy

        result = glue_object.query_with_params()

        row = result['items'][0]
        row_policy = row['policy']
        row_metadata = row['metadata']['attributes']
        self.assertTrue(policy_has_attribute(row_policy, 'form'))
        self.assertTrue(policy_has_attribute(row_policy, 'forms.default'))
        self.assertEqual(row_metadata['form']['namespace'], 'glue')
        self.assertEqual(row_metadata['form']['glue_namespace'], 'form')
        self.assertEqual(row['state']['form']['name']['value'], 'Koko')

    def test_queryset_get_returns_child_model_proxy_payload(self):
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
        policy = glue_object.policy

        row = glue_object.get(pk=gorilla.pk)

        self.assertEqual(row['policy']['namespace'], 'model')
        self.assertEqual(row['policy']['name'], f'gorillas.{gorilla.pk}')
        self.assertEqual(row['policy']['identity']['target_pk'], gorilla.pk)
        self.assertTrue(policy_has_attribute(row['policy'], 'form'))
        self.assertEqual(row['state']['name']['value'], 'Koko')

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
            target_glue_client_state={},
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
        self.assertEqual(result['items'][0]['state']['name']['value'], 'Ndume')


class PythonAdaptersTestCase(TestCase):
    def test_json_adapter_builds_signed_policy_with_normalized_value(self):
        glue_object = with_request(JsonGlue(
            [{'skill': {'name': 'Grappling'}, 'enabled': True}],
            **glue_context(name='permission_data', access=GlueAccess.VIEW),
        ))

        policy = glue_object.policy
        manifest = json.loads(json.dumps(glue_object.manifest.model_dump(), cls=GlueResponseJSONEncoder))

        self.assertEqual(policy.namespace, 'json')
        self.assertEqual(policy.identity['value'][0]['skill']['name'], 'Grappling')
        self.assertEqual(manifest['policy']['identity']['value'][0]['skill']['name'], 'Grappling')
        self.assertEqual(glue_object.metadata['type'], 'array')

    def test_json_adapter_reconstructs_from_policy(self):
        glue_object = with_request(JsonGlue(
            {'permissions': [{'name': 'auth.add_group'}]},
            **glue_context(name='permission_data', access=GlueAccess.VIEW),
        ))

        resolved = JsonGlue._reconstruct_from_policy(glue_object.policy)

        self.assertEqual(resolved.name, 'permission_data')
        self.assertEqual(resolved.target, {'permissions': [{'name': 'auth.add_group'}]})

    def test_template_adapter_builds_render_policy(self):
        glue_object = with_request(TemplateGlue(
            'template.html',
            **glue_context(name='card', access=GlueAccess.VIEW),
            initial_context_data={'name': 'Ada'},
        ))

        policy = glue_object.policy
        state = glue_object.state

        self.assertEqual(policy.namespace, 'template')
        self.assertIn('render_html', policy.attributes)
        self.assertEqual(state['context_data'], {'name': 'Ada'})

    def test_function_adapter_builds_execute_policy(self):
        glue_object = with_request(FunctionGlue(
            'django_glue.tests.glue.test_adapters.sample_function',
            **glue_context(name='sample', access=GlueAccess.VIEW),
        ))

        policy = glue_object.policy
        metadata = glue_object.metadata

        self.assertEqual(policy.namespace, 'function')
        self.assertIn('execute', policy.attributes)
        self.assertEqual(metadata['params'][0]['name'], 'amount')


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


class LazyLoadingTestCase(TestCase):
    """Tests for lazy loading behavior - state is empty in lazy manifests."""

    def test_model_lazy_manifest_has_empty_state(self):
        gorilla = Gorilla.objects.create(name='Koko')
        glue_object = with_request(ModelGlue(gorilla, **glue_context(), fields=['name']))

        manifest = glue_object.manifest.model_dump()

        self.assertIn('policy', manifest)
        self.assertIn('metadata', manifest)
        self.assertIn('state', manifest)
        self.assertEqual(manifest['state'], {})
        self.assertEqual(manifest['loading_strategy'], 'lazy')

    def test_model_load_state_attribute_returns_state(self):
        gorilla = Gorilla.objects.create(name='Koko')
        glue_object = ModelGlue(gorilla, **glue_context(), fields=['name'])

        result = glue_object.load_state()

        self.assertIn('name', result)
        self.assertEqual(result['name']['value'], 'Koko')

    def test_model_load_state_does_not_hydrate_stale_client_state(self):
        gorilla = Gorilla.objects.create(name='Koko')
        glue_object = with_request(ModelGlue(gorilla, **glue_context(), fields=['name']))
        policy = glue_object.policy
        gorilla.name = 'Ndume'
        gorilla.save()

        context = AttributeCallRequestContext.model_construct(
            request=glue_object.request,
            target_glue_policy=policy,
            target_glue_client_state={'name': {'value': 'Koko'}},
            target_attribute_name='load_state',
            target_attribute_call_kwargs={},
        )
        resolved = ModelGlue.from_attribute_call_resolver_context(context)

        result = resolved.load_state()

        self.assertEqual(result['name']['value'], 'Ndume')

    def test_form_lazy_manifest_has_empty_state(self):
        form = ContactForm(initial={'name': 'Ada', 'email': 'ada@test.com'})
        glue_object = with_request(FormGlue(form, **glue_context(name='contact', access=GlueAccess.CHANGE)))

        manifest = glue_object.manifest.model_dump()

        self.assertIn('policy', manifest)
        self.assertIn('metadata', manifest)
        self.assertIn('state', manifest)
        self.assertEqual(manifest['state'], {})
        self.assertEqual(manifest['loading_strategy'], 'lazy')

    def test_form_load_state_attribute_returns_state(self):
        form = ContactForm(initial={'name': 'Ada', 'email': 'ada@test.com'})
        glue_object = FormGlue(form, **glue_context(name='contact', access=GlueAccess.CHANGE))

        result = glue_object.load_state()

        self.assertIn('name', result)
        self.assertEqual(result['name']['value'], 'Ada')

    def test_lazy_queryset_manifest_has_empty_state(self):
        Gorilla.objects.create(name='Koko')
        queryset = Gorilla.objects.all()
        glue_object = with_request(QuerySetGlue(queryset, **glue_context(name='gorillas'), fields=['name']))

        manifest = glue_object.manifest.model_dump()

        self.assertEqual(manifest['state'], {})
        self.assertEqual(manifest['loading_strategy'], 'lazy')

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
        item = result['items'][0]
        self.assertIn('state', item)
        self.assertEqual(item['state']['name']['value'], 'Koko')


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

    def test_model_metadata_is_cached(self):
        gorilla = Gorilla.objects.create(name='Koko')
        glue_object = ModelGlue(gorilla, **glue_context(), fields=['name'])

        meta1 = glue_object.metadata
        meta2 = glue_object.metadata

        self.assertIs(meta1, meta2)

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


class ForeignKeyFieldTestCase(TestCase):
    """Tests for ForeignKey field handling in ModelGlue."""

    def setUp(self):
        self.red_gorilla = Gorilla.objects.create(name='Red Koko', age=25)
        self.blue_gorilla = Gorilla.objects.create(name='Blue Bobo', age=30)
        self.fight = Fight.objects.create(
            name='Championship',
            red_corner=self.red_gorilla,
            blue_corner=self.blue_gorilla,
        )

    def test_fk_attname_included_as_separate_field_attribute(self):
        """The FK attname (e.g., red_corner_id) should be a separate field attribute."""
        glue_object = with_request(ModelGlue(
            self.fight,
            **glue_context(name='fight'),
            fields=['name', 'red_corner'],
        ))

        attributes = glue_object.attributes

        self.assertIn('red_corner_id', attributes)
        self.assertIn('red_corner', attributes)
        # Check namespace via metadata
        self.assertEqual(attributes['red_corner_id'].metadata['namespace'], 'field')
        self.assertEqual(attributes['red_corner'].metadata['namespace'], 'related_field')

    def test_fk_attname_state_contains_raw_pk_value(self):
        """The attname field state should contain the raw FK value."""
        glue_object = with_request(ModelGlue(
            self.fight,
            **glue_context(name='fight'),
            fields=['name', 'red_corner'],
        ))

        state = glue_object.state

        self.assertIn('red_corner_id', state)
        self.assertEqual(state['red_corner_id']['value'], self.red_gorilla.pk)

    def test_eager_fk_includes_nested_state(self):
        """When FK is cached (select_related), state includes nested object state."""
        fight = Fight.objects.select_related('red_corner').get(pk=self.fight.pk)
        glue_object = with_request(ModelGlue(
            fight,
            **glue_context(name='fight'),
            fields=['name', 'red_corner'],
        ))

        state = glue_object.state

        self.assertIn('red_corner', state)
        self.assertIsInstance(state['red_corner'], dict)
        self.assertIn('name', state['red_corner'])
        self.assertEqual(state['red_corner']['name']['value'], 'Red Koko')

    def test_fk_related_field_config_limits_nested_state(self):
        fight = Fight.objects.select_related('red_corner').get(pk=self.fight.pk)
        glue_object = with_request(ModelGlue(
            fight,
            **glue_context(name='fight'),
            fields=['name', 'red_corner'],
            related_field_config={
                'red_corner': {
                    'fields': ['name'],
                },
            },
        ))

        state = glue_object.state

        self.assertIn('red_corner', state)
        self.assertIn('name', state['red_corner'])
        self.assertNotIn('age', state['red_corner'])

    def test_queryset_fk_related_field_config_limits_child_nested_state(self):
        glue_object = QuerySetGlue(
            Fight.objects.select_related('red_corner'),
            name='fights',
            access=GlueAccess.VIEW,
            fields=['name', 'red_corner'],
            related_field_config={
                'red_corner': {
                    'fields': ['name'],
                },
            },
        )
        glue_object.request = request_with_session()
        glue_object.policy

        result = glue_object.query_with_params()
        state = result['items'][0]['state']

        self.assertIn('red_corner', state)
        self.assertIn('name', state['red_corner'])
        self.assertNotIn('age', state['red_corner'])

    def test_lazy_fk_state_is_none(self):
        """When FK is not cached (lazy), state is None for the FK field."""
        # Clear the cached related instance
        fight = Fight.objects.get(pk=self.fight.pk)
        glue_object = with_request(ModelGlue(
            fight,
            **glue_context(name='fight'),
            fields=['name', 'red_corner'],
        ))

        state = glue_object.state

        # Lazy FK returns None for state (attname field has the PK)
        self.assertIn('red_corner', state)
        self.assertIsNone(state['red_corner'])

    def test_eager_fk_includes_nested_policy(self):
        """When FK is cached, policy includes nested policy object."""
        fight = Fight.objects.select_related('red_corner').get(pk=self.fight.pk)
        glue_object = with_request(ModelGlue(
            fight,
            **glue_context(name='fight'),
            fields=['name', 'red_corner'],
        ))

        policy = glue_object.policy

        # Find the nested policy for red_corner
        nested_policies = [
            attr for attr in policy.attributes
            if hasattr(attr, 'name') and 'red_corner' in attr.name
        ]
        self.assertEqual(len(nested_policies), 1)
        self.assertIn('fight.red_corner', nested_policies[0].name)

    def test_lazy_fk_includes_nested_policy(self):
        """When FK is lazy, policy still includes nested policy for loading."""
        fight = Fight.objects.get(pk=self.fight.pk)
        glue_object = with_request(ModelGlue(
            fight,
            **glue_context(name='fight'),
            fields=['name', 'red_corner'],
        ))

        policy = glue_object.policy

        # Nested policy should still exist for lazy loading
        nested_policies = [
            attr for attr in policy.attributes
            if hasattr(attr, 'name') and 'red_corner' in attr.name
        ]
        self.assertEqual(len(nested_policies), 1)

    def test_fk_metadata_includes_lazy_flag(self):
        """FK metadata should indicate whether it's lazy or eager."""
        # Lazy case
        fight_lazy = Fight.objects.get(pk=self.fight.pk)
        glue_lazy = with_request(ModelGlue(
            fight_lazy,
            **glue_context(name='fight'),
            fields=['name', 'red_corner'],
        ))

        # Eager case
        fight_eager = Fight.objects.select_related('red_corner').get(pk=self.fight.pk)
        glue_eager = with_request(ModelGlue(
            fight_eager,
            **glue_context(name='fight'),
            fields=['name', 'red_corner'],
        ))

        lazy_meta = glue_lazy.metadata['attributes']['red_corner']
        eager_meta = glue_eager.metadata['attributes']['red_corner']

        self.assertTrue(lazy_meta['lazy'])
        self.assertFalse(eager_meta['lazy'])

    def test_null_fk_has_no_nested_policy(self):
        """When FK value is null, no nested policy should be created."""
        # winner is null by default
        glue_object = with_request(ModelGlue(
            self.fight,
            **glue_context(name='fight'),
            fields=['name', 'winner'],
        ))

        policy = glue_object.policy

        # No nested policy for null FK
        nested_policies = [
            attr for attr in policy.attributes
            if hasattr(attr, 'name') and 'winner' in attr.name
        ]
        self.assertEqual(len(nested_policies), 0)

        # But winner should still be in attributes as a string
        string_attrs = [attr for attr in policy.attributes if isinstance(attr, str)]
        self.assertIn('winner', string_attrs)

    def test_null_fk_attname_state_is_none(self):
        """When FK is null, attname field state should be None."""
        glue_object = with_request(ModelGlue(
            self.fight,
            **glue_context(name='fight'),
            fields=['name', 'winner'],
        ))

        state = glue_object.state

        self.assertIn('winner_id', state)
        self.assertIsNone(state['winner_id']['value'])

    def test_all_fields_uses_fk_attname_without_nested_proxy(self):
        from django_glue.glue.objects.django.model.object import ALL_FIELDS

        glue_object = with_request(ModelGlue(
            self.fight,
            **glue_context(name='fight'),
            fields=ALL_FIELDS,
        ))

        self.assertIn('red_corner_id', glue_object._included_fields)
        self.assertNotIn('red_corner', glue_object._included_fields)
        self.assertIn('red_corner_id', glue_object.attributes)
        self.assertNotIn('red_corner', glue_object.attributes)
        self.assertEqual(glue_object.state['red_corner_id']['value'], self.red_gorilla.pk)


class RelatedSetFieldTestCase(TestCase):
    """Tests for reverse FK and M2M fields as QuerySetGlue proxies."""

    def setUp(self):
        self.gorilla = Gorilla.objects.create(name='Koko', age=25)
        self.skill1 = Skill.objects.create(name='Climbing')
        self.skill2 = Skill.objects.create(name='Swimming')
        self.gorilla.skills.add(self.skill1, self.skill2)

        # For reverse FK tests
        self.opponent = Gorilla.objects.create(name='Bobo', age=20)
        self.fight = Fight.objects.create(
            name='Fight 1',
            red_corner=self.gorilla,
            blue_corner=self.opponent,
        )

    # M2M Tests

    def test_m2m_field_creates_related_set_attribute(self):
        """M2M field should create RelatedSetFieldAttribute."""
        glue_object = with_request(ModelGlue(
            self.gorilla,
            **glue_context(name='gorilla'),
            fields=['name', 'skills'],
        ))

        self.assertIn('skills', glue_object.attributes)
        self.assertEqual(
            glue_object.attributes['skills'].metadata['namespace'],
            'related_set'
        )
        self.assertEqual(
            glue_object.attributes['skills'].metadata['relation_type'],
            'm2m'
        )

    def test_m2m_lazy_state_is_none(self):
        """When M2M is not prefetched, state should be None."""
        gorilla = Gorilla.objects.get(pk=self.gorilla.pk)
        glue_object = with_request(ModelGlue(
            gorilla,
            **glue_context(name='gorilla'),
            fields=['name', 'skills'],
        ))

        state = glue_object.state
        self.assertIsNone(state['skills'])

    def test_m2m_eager_state_includes_items(self):
        """When M2M is prefetched, state should include items."""
        gorilla = Gorilla.objects.prefetch_related('skills').get(pk=self.gorilla.pk)
        glue_object = with_request(ModelGlue(
            gorilla,
            **glue_context(name='gorilla'),
            fields=['name', 'skills'],
        ))

        state = glue_object.state
        self.assertIn('skills', state)
        self.assertIn('items', state['skills'])
        self.assertEqual(len(state['skills']['items']), 2)

    def test_m2m_includes_nested_queryset_policy(self):
        """M2M should include nested QuerySetGlue policy."""
        glue_object = with_request(ModelGlue(
            self.gorilla,
            **glue_context(name='gorilla'),
            fields=['name', 'skills'],
        ))

        policy = glue_object.policy
        nested = [
            a for a in policy.attributes
            if hasattr(a, 'name') and 'skills' in a.name
        ]

        self.assertEqual(len(nested), 1)
        self.assertEqual(nested[0].namespace, 'querySet')

    def test_m2m_metadata_includes_lazy_flag(self):
        """M2M metadata should indicate lazy vs eager."""
        # Lazy
        gorilla_lazy = Gorilla.objects.get(pk=self.gorilla.pk)
        glue_lazy = with_request(ModelGlue(
            gorilla_lazy,
            **glue_context(name='gorilla'),
            fields=['skills'],
        ))

        # Eager
        gorilla_eager = Gorilla.objects.prefetch_related('skills').get(pk=self.gorilla.pk)
        glue_eager = with_request(ModelGlue(
            gorilla_eager,
            **glue_context(name='gorilla'),
            fields=['skills'],
        ))

        self.assertTrue(glue_lazy.metadata['attributes']['skills']['lazy'])
        self.assertFalse(glue_eager.metadata['attributes']['skills']['lazy'])

    # Reverse FK Tests

    def test_reverse_fk_creates_related_set_attribute(self):
        """Reverse FK should create RelatedSetFieldAttribute."""
        glue_object = with_request(ModelGlue(
            self.gorilla,
            **glue_context(name='gorilla'),
            fields=['name', 'fights_as_red_corner'],
        ))

        self.assertIn('fights_as_red_corner', glue_object.attributes)
        self.assertEqual(
            glue_object.attributes['fights_as_red_corner'].metadata['namespace'],
            'related_set'
        )
        self.assertEqual(
            glue_object.attributes['fights_as_red_corner'].metadata['relation_type'],
            'reverse_fk'
        )

    def test_reverse_fk_lazy_state_is_none(self):
        """When reverse FK is not prefetched, state should be None."""
        gorilla = Gorilla.objects.get(pk=self.gorilla.pk)
        glue_object = with_request(ModelGlue(
            gorilla,
            **glue_context(name='gorilla'),
            fields=['name', 'fights_as_red_corner'],
        ))

        state = glue_object.state
        self.assertIsNone(state['fights_as_red_corner'])

    def test_reverse_fk_eager_state_includes_items(self):
        """When reverse FK is prefetched, state should include items."""
        gorilla = Gorilla.objects.prefetch_related('fights_as_red_corner').get(pk=self.gorilla.pk)
        glue_object = with_request(ModelGlue(
            gorilla,
            **glue_context(name='gorilla'),
            fields=['name', 'fights_as_red_corner'],
        ))

        state = glue_object.state
        self.assertIn('fights_as_red_corner', state)
        self.assertIn('items', state['fights_as_red_corner'])
        self.assertEqual(len(state['fights_as_red_corner']['items']), 1)

    def test_reverse_fk_includes_nested_queryset_policy(self):
        """Reverse FK should include nested QuerySetGlue policy."""
        glue_object = with_request(ModelGlue(
            self.gorilla,
            **glue_context(name='gorilla'),
            fields=['name', 'fights_as_red_corner'],
        ))

        policy = glue_object.policy
        nested = [
            a for a in policy.attributes
            if hasattr(a, 'name') and 'fights_as_red_corner' in a.name
        ]

        self.assertEqual(len(nested), 1)
        self.assertEqual(nested[0].namespace, 'querySet')

    # Edge Cases

    def test_unsaved_instance_m2m_has_no_nested_glue(self):
        """Unsaved instance should not have nested QuerySetGlue for M2M."""
        gorilla = Gorilla(name='New')  # Not saved
        glue_object = with_request(ModelGlue(
            gorilla,
            **glue_context(name='gorilla'),
            fields=['name', 'skills'],
        ))

        # No nested policy for unsaved instance
        policy = glue_object.policy
        nested = [
            a for a in policy.attributes
            if hasattr(a, 'name') and 'skills' in a.name
        ]
        self.assertEqual(len(nested), 0)

    def test_all_fields_excludes_relationship_proxies_by_default(self):
        from django_glue.glue.objects.django.model.object import ALL_FIELDS

        glue_object = with_request(ModelGlue(
            self.gorilla,
            **glue_context(name='gorilla'),
            fields=ALL_FIELDS,
        ))

        self.assertNotIn('skills', glue_object.attributes)
        self.assertNotIn('fights_as_red_corner', glue_object.attributes)
        self.assertNotIn('fights_as_blue_corner', glue_object.attributes)

    def test_explicit_reverse_relation_can_be_excluded(self):
        glue_object = with_request(ModelGlue(
            self.gorilla,
            **glue_context(name='gorilla'),
            fields=['name', 'fights_as_red_corner', 'fights_as_blue_corner'],
            exclude=['fights_as_red_corner', 'fights_as_blue_corner'],
        ))

        self.assertNotIn('fights_as_red_corner', glue_object.attributes)
        self.assertNotIn('fights_as_blue_corner', glue_object.attributes)
