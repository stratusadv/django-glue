from __future__ import annotations

from functools import cached_property
from types import SimpleNamespace

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import QuerySet
from django.test import TestCase

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
    GlueMetadata,
    FunctionGlue,
    GlueObjectResolverRegistry,
)
from django_glue.glue.attributes import Attribute, ContainerAttribute, GlueObjectAttribute
from django_glue.exceptions import GlueCalledStateAttributeError, GlueInvalidPolicyError
from django_glue.glue.schemas import AttributeCallResolverContext
from test_project.gorilla.models import Gorilla, Skill
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


class NestedStatsGlue(BaseGlue):
    namespace = 'stats'

    def __init__(self):
        super().__init__(name='stats', access=GlueAccess.VIEW)

    @property
    def identity(self) -> dict:
        return {'name': self.name}

    @cached_property
    def metadata(self) -> GlueMetadata:
        return GlueMetadata.from_payload({
            'attributes': {
                name: attribute.metadata
                for name, attribute in self.attributes.items()
            },
        })

    @classmethod
    def _from_policy(cls, policy):
        return cls()

    @Attribute(access=GlueAccess.VIEW)
    def score(self) -> int:
        return 42

    @Attribute(access=GlueAccess.CHANGE)
    def reset(self) -> str:
        return 'reset'


class NestedDashboardGlue(BaseGlue):
    namespace = 'dashboard'
    stats = Attribute(NestedStatsGlue(), access=GlueAccess.VIEW)

    def __init__(self):
        super().__init__(name='dashboard', access=GlueAccess.CHANGE)

    @property
    def identity(self) -> dict:
        return {'name': self.name}

    @cached_property
    def metadata(self) -> GlueMetadata:
        return GlueMetadata.from_payload({
            'attributes': {
                name: attribute.metadata
                for name, attribute in self.attributes.items()
            },
        })

    @classmethod
    def _from_policy(cls, policy):
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

        metadata = glue_object.metadata.to_payload()
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

        result = glue_object.query_with_params(kwargs={})

        self.assertEqual(len(result['items']), 1)
        row = result['items'][0]
        self.assertEqual(row['state']['name']['value'], 'Koko')
        self.assertNotIn('signature', row['state'])


class GluePolicyTestCase(TestCase):
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


class GlueShapelessPayloadTestCase(TestCase):
    def test_metadata_accepts_arbitrary_payload_shape(self):
        metadata = GlueMetadata.from_payload({'ui': {'fields': ['name']}})

        self.assertEqual(metadata.to_payload(), {'ui': {'fields': ['name']}})

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
            glue_object.metadata.to_payload()['attributes'],
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
        metadata = glue_object.metadata.to_payload()

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

        metadata = glue_object.metadata.to_payload()
        skills_metadata = metadata['attributes']['skills']

        self.assertEqual(skills_metadata['type'], 'ManyToManyField')
        self.assertEqual(skills_metadata['choices'], [])
        self.assertEqual(skills_metadata['pk_field'], Skill._meta.pk.name)
        self.assertEqual(skills_metadata['choice_model_path'], 'test_project.gorilla.models.Skill')
        self.assertIn('choices_cache_key', skills_metadata)

    def test_model_foreign_key_choices_returns_related_choices(self):
        skill = Skill.objects.create(name='Grappling')
        glue_object = ModelGlue(self.gorilla, **glue_context(), fields=['skills'])

        result = glue_object.foreign_key_choices(field_name='skills', choice_fields=['name'])

        self.assertEqual(result, [{'pk': skill.pk, '__str__': 'Grappling', 'name': 'Grappling'}])

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
            'skills': {'value': [{'pk': skill.pk, '__str__': 'Grappling'}]},
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
        policy = glue_object.policy

        state = glue_object.state

        self.assertTrue(
            state['profile_photo']['value']['name'].startswith('gorilla_photos/profile-photo')
        )
        self.assertTrue(
            state['profile_photo']['value']['url'].startswith('/media/gorilla_photos/profile-photo')
        )
        self.assertGreater(state['profile_photo']['value']['size'], 0)

    def test_model_adapter_reconstructs_model_from_policy(self):
        glue_object = with_request(ModelGlue(
            self.gorilla,
            **glue_context(access=GlueAccess.VIEW),
            fields=['id', 'name'],
        ))
        policy = glue_object.policy

        resolved = ModelGlue._from_policy(policy)

        self.assertEqual(resolved.instance, self.gorilla)

    def test_model_adapter_transfers_target_glue_attributes_to_policy(self):
        glue_object = with_request(ModelGlue(self.gorilla, **glue_context(), fields=['id', 'name']))
        policy = glue_object.policy
        metadata = glue_object.metadata.to_payload()
        state = glue_object.state

        self.assertIn('shout', policy.attributes)
        self.assertIn('services.increment_age', policy.attributes)
        self.assertEqual(metadata['attributes']['services']['namespace'], 'container')
        self.assertEqual(
            metadata['attributes']['services.increment_age']['namespace'],
            'callable',
        )
        self.assertNotIn('services', state)

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
        metadata = glue_object.metadata.to_payload()
        state = glue_object.state

        self.assertIn('form', policy.attributes)
        self.assertIn('forms.default', policy.attributes)
        self.assertIsInstance(glue_object.attributes['form'], GlueObjectAttribute)
        self.assertIs(glue_object.attributes['form'], glue_object.attributes['forms.default'])
        self.assertEqual(metadata['attributes']['form']['namespace'], 'glue')
        self.assertEqual(metadata['attributes']['form']['policy']['namespace'], 'form')
        self.assertEqual(
            metadata['attributes']['form']['policy']['name'],
            f'{glue_object.name}.forms.default',
        )
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
        metadata = glue_object.metadata.to_payload()

        self.assertNotIn('form', policy.attributes)
        self.assertIn('forms.edit', policy.attributes)
        self.assertEqual(metadata['attributes']['forms.edit']['namespace'], 'glue')
        self.assertEqual(metadata['attributes']['forms.edit']['policy']['namespace'], 'form')

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
        self.assertNotIn('form', glue_object.policy.attributes)
        self.assertNotIn('forms.default', glue_object.policy.attributes)

    def test_nested_base_glue_attributes_build_container_metadata(self):
        glue_object = with_request(NestedDashboardGlue())

        policy = glue_object.policy
        metadata = glue_object.metadata.to_payload()
        state = glue_object.state

        self.assertIn('stats', policy.attributes)
        self.assertIn('stats.score', policy.attributes)
        self.assertIn('stats.reset', policy.attributes)
        self.assertIsInstance(glue_object.attributes['stats'], ContainerAttribute)
        self.assertEqual(metadata['attributes']['stats']['namespace'], 'container')
        self.assertEqual(metadata['attributes']['stats.score']['namespace'], 'callable')
        self.assertEqual(metadata['attributes']['stats.reset']['namespace'], 'callable')
        self.assertNotIn('stats', state)

        context = AttributeCallResolverContext.model_construct(
            request=glue_object.request,
            target_glue_policy=policy,
            target_glue_client_state=None,
            target_attribute_name='stats',
            target_attribute_call_kwargs={},
        )
        with self.assertRaises(GlueCalledStateAttributeError):
            glue_object.process_attribute_call(context)


class DjangoFormGlueObjectTestCase(TestCase):
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
        metadata = glue_object.metadata.to_payload()

        self.assertEqual(policy.namespace, 'form')
        self.assertIn('validate', policy.attributes)
        self.assertIn('save', policy.attributes)
        self.assertEqual(state['name']['value'], 'Ada')
        self.assertEqual(metadata['attributes']['email']['type'], 'EmailField')

    def test_form_adapter_reconstruction_preserves_initial_data(self):
        gorilla = Gorilla.objects.create(name='Instance Name', age=12)
        glue_object = with_request(FormGlue(
            TestModelForm(
                instance=gorilla,
                initial={'name': 'Initial Name', 'age': 7},
            ),
            **glue_context(name='gorilla-form'),
        ))

        resolved = FormGlue._from_policy(glue_object.policy)

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

        resolved = FormGlue._from_policy(glue_object.policy)
        state = resolved.load()['state']

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
            glue_object.metadata.to_payload()['attributes'],
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
        metadata = glue_object.metadata.to_payload()
        resolved = QuerySetGlue._from_policy(policy)

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

        result = glue_object.query_with_params(
            kwargs={'filter': {'name': 'Koko'}},
        )

        row = result['items'][0]
        self.assertEqual(row['policy']['namespace'], 'model')
        self.assertEqual(row['policy']['name'], f'gorillas.{gorilla.pk}')
        self.assertEqual(row['state']['name']['value'], 'Koko')
        self.assertEqual(row['metadata']['attributes']['name']['type'], 'CharField')

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

        result = glue_object.query_with_params(kwargs={})

        row = result['items'][0]
        row_policy_attributes = row['policy']['attributes']
        row_metadata = row['metadata']['attributes']
        self.assertIn('form', row_policy_attributes)
        self.assertIn('forms.default', row_policy_attributes)
        self.assertEqual(row_metadata['form']['namespace'], 'glue')
        self.assertEqual(row_metadata['form']['policy']['namespace'], 'form')
        self.assertEqual(
            row_metadata['form']['policy']['name'],
            f'gorillas.{gorilla.pk}.forms.default',
        )
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
        self.assertIn('form', row['policy']['attributes'])
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

        context = AttributeCallResolverContext.model_construct(
            request=request,
            target_glue_policy=glue_object.policy,
            target_glue_client_state={},
            target_attribute_name='query_with_params',
            target_attribute_call_kwargs={
                'kwargs': {
                    'order_by': 'name',
                    'slice': {'start': 0, 'stop': 1},
                },
            },
        )
        response = glue_object.process_attribute_call(context)
        resolved = QuerySetGlue._from_policy(response['data']['policy'])
        resolved.request = request

        result = resolved.query_with_params(
            kwargs={
                'filter': {'name__icontains': 'du'},
                'order_by': '-name',
                'slice': {'start': 0, 'stop': 1},
            },
        )

        self.assertEqual(len(result['items']), 1)
        self.assertEqual(result['items'][0]['state']['name']['value'], 'Ndume')


class PythonAdaptersTestCase(TestCase):
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
        metadata = glue_object.metadata.to_payload()

        self.assertEqual(policy.namespace, 'function')
        self.assertIn('execute', policy.attributes)
        self.assertEqual(metadata['params'][0]['name'], 'amount')


class GlueObjectResolverRegistryTestCase(TestCase):
    def test_registry_resolves_glue_object_class_by_policy_namespace(self):
        registry = GlueObjectResolverRegistry()
        registry.register_glue_object_class(ModelGlue)
        gorilla = Gorilla.objects.create(name='Koko')
        policy = with_request(ModelGlue(
            gorilla,
            **glue_context(access=GlueAccess.VIEW),
            fields=['name'],
        )).policy

        resolved_class = registry.get_class_for_namespace(policy.namespace)

        self.assertIs(resolved_class, ModelGlue)


def sample_function(amount: int, tax: float = 0.0):
    return amount + tax


class LazyLoadingTestCase(TestCase):
    """Tests for lazy loading behavior - state is not included in manifests."""

    def test_model_manifest_does_not_include_state(self):
        gorilla = Gorilla.objects.create(name='Koko')
        glue_object = with_request(ModelGlue(gorilla, **glue_context(), fields=['name']))

        manifest = glue_object.manifest.model_dump()

        self.assertIn('policy', manifest)
        self.assertIn('metadata', manifest)
        self.assertNotIn('state', manifest)

    def test_model_load_attribute_returns_state(self):
        gorilla = Gorilla.objects.create(name='Koko')
        glue_object = ModelGlue(gorilla, **glue_context(), fields=['name'])

        result = glue_object.load()

        self.assertIn('state', result)
        self.assertEqual(result['state']['name']['value'], 'Koko')

    def test_model_load_does_not_hydrate_stale_client_state(self):
        gorilla = Gorilla.objects.create(name='Koko')
        glue_object = with_request(ModelGlue(gorilla, **glue_context(), fields=['name']))
        policy = glue_object.policy
        gorilla.name = 'Ndume'
        gorilla.save()

        context = AttributeCallResolverContext.model_construct(
            request=glue_object.request,
            target_glue_policy=policy,
            target_glue_client_state={'name': {'value': 'Koko'}},
            target_attribute_name='load',
            target_attribute_call_kwargs={},
        )
        resolved = ModelGlue.from_attribute_call_resolver_context(context)

        result = resolved.load()

        self.assertEqual(result['state']['name']['value'], 'Ndume')

    def test_form_manifest_does_not_include_state(self):
        form = ContactForm(initial={'name': 'Ada', 'email': 'ada@test.com'})
        glue_object = with_request(FormGlue(form, **glue_context(name='contact', access=GlueAccess.CHANGE)))

        manifest = glue_object.manifest.model_dump()

        self.assertIn('policy', manifest)
        self.assertIn('metadata', manifest)
        self.assertNotIn('state', manifest)

    def test_form_load_attribute_returns_state(self):
        form = ContactForm(initial={'name': 'Ada', 'email': 'ada@test.com'})
        glue_object = FormGlue(form, **glue_context(name='contact', access=GlueAccess.CHANGE))

        result = glue_object.load()

        self.assertIn('state', result)
        self.assertIn('name', result['state'])
        self.assertEqual(result['state']['name']['value'], 'Ada')

    def test_queryset_state_returns_empty_dict(self):
        Gorilla.objects.create(name='Koko')
        queryset = Gorilla.objects.all()
        glue_object = QuerySetGlue(queryset, **glue_context(name='gorillas'), fields=['name'])

        state = glue_object.state

        self.assertEqual(state, {})

    def test_queryset_query_with_params_returns_items_with_state(self):
        gorilla = Gorilla.objects.create(name='Koko')
        queryset = Gorilla.objects.all()
        request = request_with_session()
        glue_object = QuerySetGlue(
            queryset,
            name='gorillas',
            access=GlueAccess.VIEW,
            fields=['name'],
        )
        glue_object.request = request
        policy = glue_object.policy

        result = glue_object.query_with_params(
            kwargs={},
        )

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
