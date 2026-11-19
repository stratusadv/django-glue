from __future__ import annotations

import tempfile

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils.datastructures import MultiValueDict

from django_glue.glue.objects.django.model.object import ModelGlue
from django_glue.tests.glue.test_form_uploads import GIF
from django_glue.tests.glue.test_objects import glue_context, with_request
from test_project.gorilla.models import Gorilla


class ModelUploadTestCase(TestCase):
    def setUp(self):
        self.media_root = tempfile.TemporaryDirectory()
        self.addCleanup(self.media_root.cleanup)
        media = override_settings(MEDIA_ROOT=self.media_root.name)
        media.enable()
        self.addCleanup(media.disable)
        self.gorilla = Gorilla.objects.create(name='Koko', age=10, weight=100.0, height=1.5)
        self.gorilla.profile_photo.save('original.gif', ContentFile(GIF), save=True)

    def save_photo(self, upload: SimpleUploadedFile) -> dict:
        glue_object = with_request(ModelGlue(
            self.gorilla,
            **glue_context(),
            fields=['name', 'profile_photo'],
        ))
        glue_object.request.FILES = MultiValueDict({'profile_photo': [upload]})
        glue_object._load_client_state({'name': self.gorilla.name})
        return glue_object.save()

    def test_bytes_that_are_not_an_image_are_refused_for_an_image_field(self):
        not_an_image = SimpleUploadedFile('x.gif', b'<script>alert(1)</script>', content_type='image/gif')

        result = self.save_photo(not_an_image)

        self.gorilla.refresh_from_db()
        assert result['success'] is False
        assert list(result['errors']) == ['profile_photo']
        assert self.gorilla.profile_photo.name.startswith('gorilla_photos/original')

    def test_an_image_saves_to_an_image_field(self):
        result = self.save_photo(SimpleUploadedFile('new.gif', GIF, content_type='image/gif'))

        self.gorilla.refresh_from_db()
        assert result['success'] is True
        assert self.gorilla.profile_photo.name.startswith('gorilla_photos/new')
