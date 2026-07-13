"""
Tests for Django Glue Settings configuration.
"""
from django.test import TestCase, override_settings

from django_glue.conf import settings


class SettingsTestCase(TestCase):
    """Tests for the Settings class (conf.py)."""

    def test_returns_default_session_key(self):
        """Should return default session key."""
        value = settings.DJANGO_GLUE_SESSION_PROXY_KEY
        self.assertEqual(value, 'django_glue_proxies')

    def test_returns_default_proxy_policy_max_age(self):
        """Should return default proxy policy max age."""
        value = settings.DJANGO_GLUE_PROXY_POLICY_MAX_AGE_SECONDS
        self.assertEqual(value, 600)

    @override_settings(DJANGO_GLUE_PROXY_POLICY_MAX_AGE_SECONDS=300)
    def test_overrides_proxy_policy_max_age_with_django_setting(self):
        """Should return Django project proxy policy max age setting when configured."""
        value = settings.DJANGO_GLUE_PROXY_POLICY_MAX_AGE_SECONDS
        self.assertEqual(value, 300)

    def test_raises_for_unknown_attribute(self):
        """Should raise an error for attributes not in any settings module."""
        with self.assertRaises(Exception):
            _ = settings.NONEXISTENT_ATTRIBUTE
