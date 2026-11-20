from __future__ import annotations

import tempfile

from django import forms
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils.datastructures import MultiValueDict

from django_glue.access import GlueAccess
from django_glue.glue.objects.django.form.object import FormGlue
from django_glue.tests.glue.test_objects import glue_context, with_request
from test_project.gorilla.models import Gorilla

GIF = b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'


class GorillaPhotoForm(forms.ModelForm):
    class Meta:
        model = Gorilla
        fields = ['name', 'profile_photo']
        glue_default_save = True


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class AttachmentsForm(forms.Form):
    attachments = forms.FileField(widget=MultipleFileInput, required=False)


def upload(name: str) -> SimpleUploadedFile:
    return SimpleUploadedFile(name, GIF, content_type='image/gif')


class FormUploadTestCase(TestCase):
    def setUp(self):
        self.media_root = tempfile.TemporaryDirectory()
        self.addCleanup(self.media_root.cleanup)
        media = override_settings(MEDIA_ROOT=self.media_root.name)
        media.enable()
        self.addCleanup(media.disable)
        self.gorilla = Gorilla.objects.create(name='Koko', age=10, weight=100.0, height=1.5)
        self.gorilla.profile_photo.save('original.gif', ContentFile(GIF), save=True)

    def photo_form(self, editable, files) -> FormGlue:
        glue_object = with_request(FormGlue(
            GorillaPhotoForm(instance=self.gorilla),
            **glue_context(name='photo_form', access=GlueAccess.CHANGE),
            editable=editable,
        ))
        glue_object.request.FILES = MultiValueDict(files)
        return glue_object

    def test_an_upload_to_a_field_that_is_not_editable_is_ignored(self):
        glue_object = self.photo_form(('name',), {'profile_photo': [upload('evil.gif')]})

        result = glue_object.save()

        self.gorilla.refresh_from_db()
        assert result['valid'] is True
        assert self.gorilla.profile_photo.name.startswith('gorilla_photos/original')

    def test_an_upload_to_an_editable_field_saves(self):
        glue_object = self.photo_form(('name', 'profile_photo'), {'profile_photo': [upload('new.gif')]})

        result = glue_object.save()

        self.gorilla.refresh_from_db()
        assert result['valid'] is True
        assert self.gorilla.profile_photo.name.startswith('gorilla_photos/new')

    def test_an_editable_multiple_file_field_receives_every_file(self):
        glue_object = with_request(FormGlue(
            AttachmentsForm(),
            **glue_context(name='attachments_form', access=GlueAccess.ADD),
        ))
        glue_object.request.FILES = MultiValueDict({'attachments': [upload('a.gif'), upload('b.gif')]})

        bound = glue_object._bind_form()

        assert [file.name for file in bound.files.getlist('attachments')] == ['a.gif', 'b.gif']
