import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.settings')
django.setup()

from io import BytesIO
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.test import TestCase
from PIL import Image

from django_glue.access.access import GlueAccess
from django_glue.tests.proxies.model.helpers import make_model_proxy
from test_project.gorilla.models import Gorilla, Skill
from test_project.test_forms import TestModelForm


class GlueModelInstanceProxyBoundAttributesTestCase(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.settings_override = override_settings(MEDIA_ROOT=self.media_root)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.addCleanup(lambda: shutil.rmtree(self.media_root, ignore_errors=True))
        self.gorilla = Gorilla.objects.create(
            name='Test Gorilla',
            description='Test',
            age=25,
            weight=350.0,
            height=1.8,
        )

    def test_get_returns_model_dict(self):
        proxy = make_model_proxy(self.gorilla)

        result = proxy.get(request=None)

        self.assertEqual(result['name'], 'Test Gorilla')
        self.assertEqual(result['age'], 25)

    def test_get_respects_fields_filter(self):
        proxy = make_model_proxy(self.gorilla, fields=['name', 'age'])

        result = proxy.get(request=None)

        self.assertEqual(set(result), {'name', 'age'})

    def test_get_includes_default_non_editable_fields(self):
        proxy = make_model_proxy(self.gorilla)

        result = proxy.get(request=None)
        fields = proxy._custom_policy_details['included_fields']
        state_data = proxy.serialize_state()['instance_data']

        self.assertEqual(result['created_at'], self.gorilla.created_at)
        self.assertEqual(result['updated_at'], self.gorilla.updated_at)
        self.assertIn('T', state_data['created_at'])
        self.assertIn('created_at', fields)
        self.assertFalse(fields['created_at']['editable'])
        self.assertTrue(fields['created_at']['disabled'])

    def test_non_editable_fields_do_not_join_generated_model_form(self):
        proxy = make_model_proxy(self.gorilla, fields=['name', 'created_at'])

        result = proxy.get(request=None)

        self.assertEqual(set(result), {'name', 'created_at'})
        self.assertEqual(list(proxy.state.form.fields), ['name'])

    def test_get_respects_exclude_filter(self):
        proxy = make_model_proxy(self.gorilla, exclude=['description', 'age'])

        result = proxy.get(request=None)

        self.assertNotIn('description', result)
        self.assertNotIn('age', result)

    def test_save_persists_bound_form(self):
        proxy = make_model_proxy(self.gorilla, access=GlueAccess.CHANGE)
        proxy.state.form = proxy.state.form.__class__(
            data={
                'name': 'Updated',
                'description': 'Changed',
                'age': 26,
                'weight': 360.0,
                'height': 1.9,
                'rank_points': 0,
            },
            instance=self.gorilla,
        )

        proxy.save(request=None)

        self.gorilla.refresh_from_db()
        self.assertEqual(self.gorilla.name, 'Updated')
        self.assertEqual(self.gorilla.age, 26)

    def test_delete_removes_instance(self):
        pk = self.gorilla.pk
        proxy = make_model_proxy(self.gorilla, access=GlueAccess.DELETE)

        proxy.delete(request=None)

        self.assertFalse(Gorilla.objects.filter(pk=pk).exists())

    def test_bound_attributes_have_expected_access(self):
        proxy = make_model_proxy(self.gorilla, access=GlueAccess.DELETE)
        bound_attributes = proxy.discover_bound_attributes()

        self.assertEqual(bound_attributes['GlueModelInstanceProxy.get'].required_access, GlueAccess.VIEW)
        self.assertEqual(bound_attributes['GlueModelInstanceProxy.save'].required_access, GlueAccess.CHANGE)
        self.assertEqual(bound_attributes['GlueModelInstanceProxy.delete'].required_access, GlueAccess.DELETE)

    def test_custom_form_class_path_is_preserved(self):
        proxy = make_model_proxy(self.gorilla, access=GlueAccess.CHANGE, form_class=TestModelForm)

        self.assertEqual(
            proxy._custom_policy_details['form_class_path'],
            'test_project.test_forms.TestModelForm',
        )

    def test_state_serializes_image_fields_as_metadata(self):
        image = BytesIO()
        Image.new('RGB', (10, 10), (255, 0, 0)).save(image, format='PNG')
        self.gorilla.profile_photo.save(
            'profile-photo.png',
            SimpleUploadedFile('profile-photo.png', image.getvalue(), content_type='image/png'),
        )
        proxy = make_model_proxy(self.gorilla, access=GlueAccess.CHANGE)

        profile_photo = proxy.state.serialize()['instance_data']['profile_photo']

        self.assertEqual(profile_photo['name'], 'gorilla_photos/profile-photo.png')
        self.assertEqual(profile_photo['url'], '/media/gorilla_photos/profile-photo.png')
        self.assertGreater(profile_photo['size'], 0)

    def test_state_serializes_model_multiple_choice_values_as_choice_objects(self):
        skill = Skill.objects.create(name='Grappling')
        self.gorilla.skills.add(skill)
        proxy = make_model_proxy(self.gorilla, access=GlueAccess.CHANGE)

        skills = proxy.state.serialize()['instance_data']['skills']

        self.assertEqual(skills, [{'pk': skill.pk, '__str__': 'Grappling'}])

    def test_save_persists_uploaded_image_file(self):
        image = BytesIO()
        Image.new('RGB', (10, 10), (255, 0, 0)).save(image, format='PNG')
        upload = SimpleUploadedFile(
            'profile-photo.png',
            image.getvalue(),
            content_type='image/png',
        )
        proxy = make_model_proxy(self.gorilla, access=GlueAccess.CHANGE)
        proxy.state.form = proxy.state.form.__class__(
            data={
                'name': self.gorilla.name,
                'description': self.gorilla.description,
                'age': self.gorilla.age,
                'weight': self.gorilla.weight,
                'height': self.gorilla.height,
                'rank_points': self.gorilla.rank_points,
            },
            files={'profile_photo': upload},
            instance=self.gorilla,
        )

        proxy.save(request=None)

        self.gorilla.refresh_from_db()
        self.assertTrue(self.gorilla.profile_photo)
        self.assertTrue(self.gorilla.profile_photo.name.startswith('gorilla_photos/profile-photo'))
