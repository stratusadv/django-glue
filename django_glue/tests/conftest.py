"""
Pytest configuration for Django Glue tests.

This conftest.py handles Django setup automatically for all tests,
eliminating the need for boilerplate in each test file.
"""
import os

import django
import pytest
from django.test import RequestFactory


def pytest_configure():
    """Configure Django settings before tests run."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.base_settings')
    django.setup()


class MockSession(dict):
    """A dict subclass that has a modified attribute like Django sessions."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.modified = False


@pytest.fixture
def request_factory():
    """Return a Django RequestFactory instance."""
    return RequestFactory()


@pytest.fixture
def mock_request(request_factory):
    """Return a mock request with session."""
    request = request_factory.get('/')
    request.session = MockSession()
    return request


@pytest.fixture
def sample_task(db):
    """Create and return a sample Task for testing."""
    from test_project.task.models import Task
    return Task.objects.create(
        title='Test Task',
        description='A task for testing',
        done=False,
        order=42
    )


@pytest.fixture
def sample_tasks(db):
    """Create and return multiple sample Tasks for testing."""
    from test_project.task.models import Task
    tasks = []
    for i in range(5):
        tasks.append(Task.objects.create(
            title=f'Task {i}',
            description=f'Description {i}',
            done=i % 2 == 0,
            order=i + 1
        ))
    return tasks