"""
Tests for Django Glue Settings configuration.
"""
from django.test import TestCase, override_settings

from django_glue.conf import settings
from django_glue import settings as default_settings


class SettingsTestCase(TestCase):
    """Tests for the Settings class (conf.py)."""

    def test_returns_default_setting(self):
        """Should return default setting when not overridden in Django settings."""
        value = settings.DJANGO_GLUE_KEEP_LIVE_INTERVAL_TIME_SECONDS
        self.assertEqual(value, 600)

    def test_returns_default_session_key(self):
        """Should return default session key."""
        value = settings.DJANGO_GLUE_SESSION_PROXY_KEY
        self.assertEqual(value, 'django_glue_proxies')

    def test_returns_default_expiry_message(self):
        """Should return default session expiry message."""
        value = settings.DJANGO_GLUE_SESSION_EXPIRY_MESSAGE
        self.assertEqual(value, 'Session expired. Do you want to reload the page?')

    @override_settings(DJANGO_GLUE_KEEP_LIVE_INTERVAL_TIME_SECONDS=300)
    def test_overrides_with_django_setting(self):
        """Should return Django project setting when it overrides the default."""
        value = settings.DJANGO_GLUE_KEEP_LIVE_INTERVAL_TIME_SECONDS
        self.assertEqual(value, 300)

    def test_raises_for_unknown_attribute(self):
        """Should raise an error for attributes not in any settings module."""
        with self.assertRaises(Exception):
            _ = settings.NONEXISTENT_ATTRIBUTE
