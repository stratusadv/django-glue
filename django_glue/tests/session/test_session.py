"""
Tests for Django Glue GlueSession proxy management.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.base_settings')
django.setup()

from time import time

from django.test import TestCase, RequestFactory

from django_glue.session import GlueSession
from django_glue.access.access import GlueAccess
from django_glue.proxies.model import GlueModelProxy
from django_glue.proxies.queryset import GlueQuerySetProxy
from django_glue.exceptions import GlueProxyNotFoundError
from django_glue import settings
from test_project.task.models import Task


class MockSession(dict):
    """A dict subclass that also has a modified attribute like Django sessions."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.modified = False


class GlueSessionInitTestCase(TestCase):
    """Tests for GlueSession initialization."""

    def setUp(self):
        """Create a mock request with session."""
        self.factory = RequestFactory()
        self.request = self.factory.get('/')
        self.request.session = MockSession()

    def test_init_creates_proxy_registry(self):
        """__init__ should create proxy_registry in session."""
        session = GlueSession(self.request)

        self.assertIn(settings.DJANGO_GLUE_SESSION_PROXY_KEY, self.request.session)
        self.assertEqual(session.proxy_registry, {})

    def test_init_creates_keep_live_registry(self):
        """__init__ should create keep_live_registry in session."""
        session = GlueSession(self.request)

        self.assertIn(settings.DJANGO_GLUE_SESSION_KEEP_LIVE_KEY, self.request.session)
        self.assertEqual(session.keep_live_registry, {})

    def test_init_uses_existing_registries(self):
        """__init__ should reuse existing session registries."""
        self.request.session[settings.DJANGO_GLUE_SESSION_PROXY_KEY] = {'existing': 'data'}
        self.request.session[settings.DJANGO_GLUE_SESSION_KEEP_LIVE_KEY] = {'existing': 123.0}

        session = GlueSession(self.request)

        self.assertEqual(session.proxy_registry, {'existing': 'data'})
        self.assertEqual(session.keep_live_registry, {'existing': 123.0})


class GlueSessionRegisterProxyTestCase(TestCase):
    """Tests for GlueSession.register_proxy()."""

    def setUp(self):
        """Create a mock request with session and test task."""
        self.factory = RequestFactory()
        self.request = self.factory.get('/')
        self.request.session = MockSession()

        self.task = Task.objects.create(
            title='Test Task',
            description='Test description',
            done=False,
            order=1
        )

    def test_register_proxy_adds_to_registry(self):
        """register_proxy should add proxy session data to registry."""
        session = GlueSession(self.request)
        proxy = GlueModelProxy(
            target=self.task,
            unique_name='task',
            access=GlueAccess.VIEW,
        )

        session.register_proxy(proxy)

        self.assertIn('task', session.proxy_registry)

    def test_register_proxy_sets_keep_live_time(self):
        """register_proxy should set expiration time in keep_live_registry."""
        session = GlueSession(self.request)
        proxy = GlueModelProxy(
            target=self.task,
            unique_name='task',
            access=GlueAccess.VIEW,
        )

        before_time = time()
        session.register_proxy(proxy)
        after_time = time()

        expire_time = session.keep_live_registry['task']
        expected_min = before_time + settings.DJANGO_GLUE_KEEP_LIVE_INTERVAL_TIME_SECONDS
        expected_max = after_time + settings.DJANGO_GLUE_KEEP_LIVE_INTERVAL_TIME_SECONDS

        self.assertGreaterEqual(expire_time, expected_min)
        self.assertLessEqual(expire_time, expected_max)

    def test_register_proxy_marks_session_modified(self):
        """register_proxy should set request.session.modified = True."""
        session = GlueSession(self.request)
        proxy = GlueModelProxy(
            target=self.task,
            unique_name='task',
            access=GlueAccess.VIEW,
        )

        session.register_proxy(proxy)

        self.assertTrue(self.request.session.modified)


class GlueSessionGetProxyTestCase(TestCase):
    """Tests for GlueSession.get_proxy_by_unique_name()."""

    def setUp(self):
        """Create a mock request with session and test task."""
        self.factory = RequestFactory()
        self.request = self.factory.get('/')
        self.request.session = MockSession()

        self.task = Task.objects.create(
            title='Test Task',
            description='Test description',
            done=False,
            order=1
        )

    def test_get_proxy_returns_model_proxy(self):
        """get_proxy_by_unique_name should return GlueModelProxy for model."""
        session = GlueSession(self.request)
        original_proxy = GlueModelProxy(
            target=self.task,
            unique_name='task',
            access=GlueAccess.VIEW,
        )
        session.register_proxy(original_proxy)

        retrieved_proxy = session.get_proxy_by_unique_name('task')

        self.assertIsInstance(retrieved_proxy, GlueModelProxy)
        self.assertEqual(retrieved_proxy.unique_name, 'task')

    def test_get_proxy_returns_queryset_proxy(self):
        """get_proxy_by_unique_name should return GlueQuerySetProxy for queryset."""
        session = GlueSession(self.request)
        original_proxy = GlueQuerySetProxy(
            target=Task.objects.all(),
            unique_name='tasks',
            access=GlueAccess.VIEW,
        )
        session.register_proxy(original_proxy)

        retrieved_proxy = session.get_proxy_by_unique_name('tasks')

        self.assertIsInstance(retrieved_proxy, GlueQuerySetProxy)
        self.assertEqual(retrieved_proxy.unique_name, 'tasks')

    def test_get_proxy_raises_not_found(self):
        """get_proxy_by_unique_name should raise GlueProxyNotFoundError for missing name."""
        session = GlueSession(self.request)

        with self.assertRaises(GlueProxyNotFoundError) as context:
            session.get_proxy_by_unique_name('nonexistent')

        self.assertEqual(context.exception.unique_name, 'nonexistent')


class GlueSessionExpirationTestCase(TestCase):
    """Tests for GlueSession expiration handling."""

    def setUp(self):
        """Create a mock request with session and test task."""
        self.factory = RequestFactory()
        self.request = self.factory.get('/')
        self.request.session = MockSession()

        self.task = Task.objects.create(
            title='Test Task',
            description='Test description',
            done=False,
            order=1
        )

    def test_proxy_is_expired_returns_false_for_valid(self):
        """_proxy_is_expired should return False for non-expired proxy."""
        session = GlueSession(self.request)
        proxy = GlueModelProxy(
            target=self.task,
            unique_name='task',
            access=GlueAccess.VIEW,
        )
        session.register_proxy(proxy)

        self.assertFalse(session._proxy_is_expired('task'))

    def test_proxy_is_expired_returns_true_for_expired(self):
        """_proxy_is_expired should return True for expired proxy."""
        session = GlueSession(self.request)
        # Manually set an expired time
        session.keep_live_registry['task'] = time() - 100  # 100 seconds ago

        self.assertTrue(session._proxy_is_expired('task'))

    def test_purge_expired_proxies_removes_expired(self):
        """purge_expired_proxies should remove expired proxies."""
        session = GlueSession(self.request)
        proxy = GlueModelProxy(
            target=self.task,
            unique_name='task',
            access=GlueAccess.VIEW,
        )
        session.register_proxy(proxy)

        # Force expire the proxy
        session.keep_live_registry['task'] = time() - 100

        session.purge_expired_proxies()

        self.assertNotIn('task', session.proxy_registry)
        self.assertNotIn('task', session.keep_live_registry)

    def test_purge_expired_proxies_keeps_valid(self):
        """purge_expired_proxies should keep non-expired proxies."""
        session = GlueSession(self.request)
        proxy = GlueModelProxy(
            target=self.task,
            unique_name='task',
            access=GlueAccess.VIEW,
        )
        session.register_proxy(proxy)

        session.purge_expired_proxies()

        self.assertIn('task', session.proxy_registry)
        self.assertIn('task', session.keep_live_registry)

    def test_purge_marks_session_modified(self):
        """purge_expired_proxies should set request.session.modified = True."""
        session = GlueSession(self.request)
        self.request.session.modified = False

        session.purge_expired_proxies()

        self.assertTrue(self.request.session.modified)


class GlueSessionRenewalTestCase(TestCase):
    """Tests for GlueSession.renew_proxies()."""

    def setUp(self):
        """Create a mock request with session and test task."""
        self.factory = RequestFactory()
        self.request = self.factory.get('/')
        self.request.session = MockSession()

        self.task = Task.objects.create(
            title='Test Task',
            description='Test description',
            done=False,
            order=1
        )

    def test_renew_proxies_updates_expire_time(self):
        """renew_proxies should update expiration time for specified proxies."""
        session = GlueSession(self.request)
        proxy = GlueModelProxy(
            target=self.task,
            unique_name='task',
            access=GlueAccess.VIEW,
        )
        session.register_proxy(proxy)

        # Set a low expire time
        old_expire_time = time() + 10
        session.keep_live_registry['task'] = old_expire_time

        session.renew_proxies(['task'])

        new_expire_time = session.keep_live_registry['task']
        self.assertGreater(new_expire_time, old_expire_time)

    def test_renew_proxies_ignores_unknown_names(self):
        """renew_proxies should silently ignore unknown proxy names."""
        session = GlueSession(self.request)

        # Should not raise
        session.renew_proxies(['nonexistent'])

    def test_renew_marks_session_modified(self):
        """renew_proxies should set request.session.modified = True."""
        session = GlueSession(self.request)
        self.request.session.modified = False

        session.renew_proxies([])

        self.assertTrue(self.request.session.modified)