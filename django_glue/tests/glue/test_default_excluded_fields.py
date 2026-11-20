from __future__ import annotations

from types import SimpleNamespace

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from django_glue.access import GlueAccess
from django_glue.glue.objects.django.model.object import ModelGlue
from django_glue.glue.objects.django.queryset import QuerySetGlue


def request_with_session(session_key='test-session'):
    return SimpleNamespace(session=SimpleNamespace(session_key=session_key), FILES={}, path_info='/')


def bound(glue_object):
    glue_object.request = request_with_session()
    glue_object.policy
    return glue_object


class DefaultExcludedFieldsTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='correct horse')

    def users(self, **kwargs):
        return bound(QuerySetGlue(
            User.objects.all(),
            name='users',
            access=GlueAccess.VIEW,
            **kwargs,
        ))

    def test_all_fields_leave_the_password_hash_out_of_a_queryset_row(self):
        row = self.users(fields='__all__').get(pk=self.user.pk)

        assert 'username' in row.state
        assert 'password' not in row.state

    def test_all_fields_offer_no_query_on_the_password_hash(self):
        query = self.users(fields='__all__').policy.capability.query

        assert 'username' in query.filters
        assert 'password' not in query.filters
        assert 'password' not in query.ordering

    def test_all_fields_do_not_make_the_password_hash_editable(self):
        glue_object = bound(ModelGlue(
            self.user,
            name='user',
            access=GlueAccess.CHANGE,
            fields='__all__',
        ))

        assert 'username' in glue_object.editable
        assert 'password' not in glue_object.editable
        assert 'password' not in glue_object.state

    def test_a_named_password_field_is_still_exposed(self):
        glue_object = bound(ModelGlue(
            self.user,
            name='user',
            access=GlueAccess.VIEW,
            fields=['username', 'password'],
        ))

        assert 'password' in glue_object.state

    @override_settings(DJANGO_GLUE_DEFAULT_EXCLUDED_MODEL_FIELD_NAMES=('username',))
    def test_the_setting_chooses_which_fields_all_leaves_out(self):
        glue_object = bound(ModelGlue(
            self.user,
            name='user',
            access=GlueAccess.VIEW,
            fields='__all__',
        ))

        assert 'username' not in glue_object.state
        assert 'password' in glue_object.state
