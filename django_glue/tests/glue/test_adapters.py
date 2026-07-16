from __future__ import annotations

from types import SimpleNamespace

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import QuerySet
from django.test import TestCase

from django_glue.access import GlueAccess
from django_glue.glue import (
    DjangoFormFieldGlue,
    DjangoModelFieldGlueAttribute,
    FormGlue,
    ModelGlue,
    QuerySetGlue,
    TemplateGlue,
    GluePolicy,
    GlueMetadata,
    FunctionGlue,
    GlueObjectResolverRegistry,
)
from django_glue.exceptions import GlueInvalidPolicyError
from test_project.gorilla.models import Gorilla, Skill
from test_project.test_forms import ContactForm


def request_with_session(session_key='test-session'):
    return SimpleNamespace(session=SimpleNamespace(session_key=session_key), FILES={})


def glue_context(name='gorilla', access=GlueAccess.CHANGE, session_key='test-session'):
    return {
        'request': request_with_session(session_key),
        'name': name,
        'access': access,
    }


class GluePolicyTestCase(TestCase):
    def test_signed_policy_validates_without_preserving_proxy_policy_shape(self):
        policy = GluePolicy.new_signed_policy({
            'session_id': 'test-session',
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
        field = Gorilla._meta.get_field('created_at')
        attribute = DjangoModelFieldGlueAttribute(
            name='created_at',
            field=field,
            instance=self.gorilla,
            access=GlueAccess.VIEW,
        )

        glue_object = ModelGlue(self.gorilla, **glue_context(access=GlueAccess.VIEW))

        self.assertEqual(glue_object.attributes['created_at'].required_access, GlueAccess.VIEW)
        self.assertFalse(glue_object.attributes['created_at'].is_callable)
        self.assertEqual(attribute.metadata['type'], 'DateTimeField')
        self.assertFalse(attribute.metadata['editable'])

    def test_model_adapter_builds_policy_state_and_metadata(self):
        glue_object = ModelGlue(
            self.gorilla,
            **glue_context(),
            fields=['id', 'name', 'created_at'],
        )
        policy = glue_object.policy
        state = glue_object.state
        metadata = glue_object.metadata.to_payload()

        self.assertEqual(policy.namespace, 'model')
        self.assertEqual(policy.identity['target_pk'], self.gorilla.pk)
        self.assertIn('save', policy.attributes)
        self.assertIn('delete', policy.attributes)
        self.assertEqual(state['instance_data']['name'], 'Koko')
        self.assertEqual(metadata['fields']['name']['type'], 'CharField')
        self.assertFalse(metadata['fields']['name']['disabled'])
        self.assertEqual(metadata['fields']['created_at']['type'], 'DateTimeField')
        self.assertTrue(metadata['fields']['created_at']['disabled'])

    def test_model_relation_field_metadata_has_stable_choice_shape(self):
        glue_object = ModelGlue(self.gorilla, **glue_context(), fields=['skills'])

        metadata = glue_object.metadata.to_payload()
        skills_metadata = metadata['fields']['skills']

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
        glue_object = ModelGlue(
            self.gorilla,
            **glue_context(),
            fields=['name', 'age', 'weight', 'height', 'profile_photo', 'skills'],
        )
        policy = glue_object.policy

        result = glue_object.save(
            state={
                'instance_data': {
                    'name': 'Ndume',
                    'age': 22,
                    'weight': 162.2,
                    'height': 1.5,
                    'profile_photo': {'name': 'existing.png', 'url': '/media/existing.png'},
                    'skills': [{'pk': skill.pk, '__str__': 'Grappling'}],
                }
            },
            policy=policy,
            request=request_with_session(),
        )

        self.gorilla.refresh_from_db()
        self.assertTrue(result['valid'])
        self.assertEqual(self.gorilla.name, 'Ndume')
        self.assertEqual(list(self.gorilla.skills.all()), [skill])

    def test_model_save_persists_nested_state_file_upload(self):
        glue_object = ModelGlue(
            self.gorilla,
            **glue_context(),
            fields=['name', 'age', 'weight', 'height', 'profile_photo'],
        )
        policy = glue_object.policy
        request = request_with_session()
        request.FILES = {
            'instance_data.profile_photo': SimpleUploadedFile(
                'profile-photo.gif',
                b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;',
                content_type='image/gif',
            )
        }

        result = glue_object.save(
            state={
                'instance_data': {
                    'name': self.gorilla.name,
                    'age': self.gorilla.age,
                    'weight': self.gorilla.weight,
                    'height': self.gorilla.height,
                }
            },
            policy=policy,
            request=request,
        )

        self.gorilla.refresh_from_db()
        self.assertTrue(result['valid'])
        self.assertTrue(self.gorilla.profile_photo)
        self.assertTrue(self.gorilla.profile_photo.name.startswith('gorilla_photos/profile-photo'))

    def test_model_adapter_serializes_file_field_values_for_initial_state(self):
        self.gorilla.profile_photo.save(
            'profile-photo.png',
            ContentFile(b'image-bytes'),
            save=True,
        )
        glue_object = ModelGlue(
            self.gorilla,
            **glue_context(access=GlueAccess.VIEW),
            fields=['profile_photo'],
        )
        policy = glue_object.policy

        state = glue_object.state

        self.assertTrue(
            state['instance_data']['profile_photo']['name'].startswith('gorilla_photos/profile-photo')
        )
        self.assertTrue(
            state['instance_data']['profile_photo']['url'].startswith('/media/gorilla_photos/profile-photo')
        )
        self.assertGreater(state['instance_data']['profile_photo']['size'], 0)

    def test_model_adapter_reconstructs_model_from_policy(self):
        glue_object = ModelGlue(self.gorilla, **glue_context(access=GlueAccess.VIEW))
        policy = glue_object.policy

        resolved = ModelGlue.from_policy(policy, request_with_session())

        self.assertEqual(resolved.instance, self.gorilla)

    def test_model_adapter_transfers_target_glue_attributes_to_policy(self):
        glue_object = ModelGlue(self.gorilla, **glue_context(), fields=['id', 'name'])
        policy = glue_object.policy

        self.assertIn('shout', policy.attributes)
        self.assertIn('services.increment_age', policy.attributes)

        shout_result = glue_object.call_attribute(
            state=None,
            attribute_name='shout',
            kwargs={'volume': 5},
            policy=policy,
            request=request_with_session(),
        )

        self.assertEqual(shout_result, 'AAAAA')


class DjangoFormGlueObjectTestCase(TestCase):
    def test_form_field_adapter_builds_metadata(self):
        form = ContactForm()
        field = form.fields['name']
        attribute = DjangoFormFieldGlue(
            name='name',
            field=field,
            form=form,
            access=GlueAccess.CHANGE,
        )

        glue_object = FormGlue(form, **glue_context(name='contact'))

        self.assertEqual(glue_object.attributes['name'].required_access, GlueAccess.CHANGE)
        self.assertFalse(glue_object.attributes['name'].is_callable)
        self.assertEqual(attribute.metadata['type'], 'CharField')
        self.assertEqual(attribute.metadata['max_length'], 100)

    def test_form_adapter_builds_policy_state_and_metadata(self):
        form = ContactForm(initial={'name': 'Ada'})
        glue_object = FormGlue(form, **glue_context(name='contact'))

        policy = glue_object.policy
        state = glue_object.state
        metadata = glue_object.metadata.to_payload()

        self.assertEqual(policy.namespace, 'form')
        self.assertIn('validate', policy.attributes)
        self.assertIn('save', policy.attributes)
        self.assertEqual(state['instance_data'], {'name': 'Ada'})
        self.assertEqual(metadata['fields']['email']['type'], 'EmailField')


class DjangoQuerySetGlueObjectTestCase(TestCase):
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
        glue_object = QuerySetGlue(
            queryset,
            **glue_context(name='gorillas', access=GlueAccess.VIEW),
            fields=['id', 'name', 'skills'],
        )

        policy = glue_object.policy
        metadata = glue_object.metadata.to_payload()
        resolved = QuerySetGlue.from_policy(policy, request_with_session())

        self.assertEqual(policy.namespace, 'querySet')
        self.assertIn('query_with_params', policy.attributes)
        self.assertIn('new', policy.attributes)
        self.assertEqual(metadata['fields']['skills']['type'], 'ManyToManyField')
        self.assertEqual(list(resolved.queryset), [gorilla])

    def test_queryset_query_returns_child_model_proxy_payloads(self):
        gorilla = Gorilla.objects.create(name='Koko')
        queryset = Gorilla.objects.filter(pk=gorilla.pk)
        request = request_with_session()
        glue_object = QuerySetGlue(
            queryset,
            request=request,
            name='gorillas',
            access=GlueAccess.CHANGE,
            fields=['id', 'name'],
        )
        policy = glue_object.policy

        result = glue_object.call_attribute(
            state=None,
            attribute_name='query_with_params',
            kwargs={'filter': {'name': 'Koko'}},
            policy=policy,
            request=request,
        )

        row = result['items'][0]
        self.assertEqual(row['policy']['namespace'], 'model')
        self.assertEqual(row['policy']['name'], f'gorillas.{gorilla.pk}')
        self.assertEqual(row['state']['instance_data']['name'], 'Koko')
        self.assertEqual(row['metadata']['fields']['name']['type'], 'CharField')


class PythonAdaptersTestCase(TestCase):
    def test_template_adapter_builds_render_policy(self):
        glue_object = TemplateGlue(
            'template.html',
            **glue_context(name='card', access=GlueAccess.VIEW),
            initial_context_data={'name': 'Ada'},
        )

        policy = glue_object.policy
        state = glue_object.state

        self.assertEqual(policy.namespace, 'template')
        self.assertIn('render_html', policy.attributes)
        self.assertEqual(state['context_data'], {'name': 'Ada'})

    def test_function_adapter_builds_execute_policy(self):
        glue_object = FunctionGlue(
            'django_glue.tests.glue.test_adapters.sample_function',
            **glue_context(name='sample', access=GlueAccess.VIEW),
        )

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
        policy = ModelGlue(
            gorilla,
            **glue_context(access=GlueAccess.VIEW),
            fields=['name'],
        ).policy

        resolved_object = registry.get_object_for_policy(policy, request_with_session())

        self.assertIsInstance(resolved_object, ModelGlue)
        self.assertEqual(resolved_object.instance.name, 'Koko')


def sample_function(amount: int, tax: float = 0.0):
    return amount + tax
