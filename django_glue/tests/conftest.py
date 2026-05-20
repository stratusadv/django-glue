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
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.settings')
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
    """Create and return a sample Gorilla for testing."""
    from test_project.gorilla.models import Gorilla

    return Gorilla.objects.create(
        name='Test Gorilla', description='A gorilla for testing', age=25, weight=350.0, height=1.8
    )


@pytest.fixture
def sample_tasks(db):
    """Create and return multiple sample Gorillas for testing."""
    from test_project.gorilla.models import Gorilla

    gorillas = []
    for i in range(5):
        gorillas.append(
            Gorilla.objects.create(
                name=f'Gorilla {i}',
                description=f'Description {i}',
                age=18 + i,
                weight=200.0 + i * 10,
                height=1.8,
            )
        )
    return gorillas
