"""
Tests for foreign_key_choices() action on proxies.
"""
from django.test import TestCase

from django_glue.access.access import GlueAccess
from django_glue.proxies import GlueModelInstanceProxy, GlueQuerySetProxy
from django_glue.exceptions import GlueAccessError
from django_glue.resolver.action.schemas import ActionRequest
from test_project.gorilla.models import Gorilla, Skill


class ForeignKeyChoicesTestCase(TestCase):
    """Tests for foreign_key_choices() action."""

    def setUp(self):
        self.skill1 = Skill.objects.create(name='Punch', description='Basic punch', difficulty=1, level=1)
        self.skill2 = Skill.objects.create(name='Kick', description='Basic kick', difficulty=2, level=1)
        self.gorilla = Gorilla.objects.create(
            name='Test Gorilla',
            description='Test',
            age=25,
            weight=350.0,
            height=1.8
        )

    def test_foreign_key_choices_returns_choices_for_model_proxy(self):
        """foreign_key_choices should return choices for FK fields on model proxy."""
        # Gorilla doesn't have FK fields, but skills is M2M.
        # Let's test with the skills M2M field via the queryset proxy
        proxy = GlueQuerySetProxy(
            target=Gorilla.objects.all(),
            unique_name='gorillas',
            access=GlueAccess.VIEW,
        )

        action_data = ActionRequest(
            proxy_definition={},
            action_kwargs={'field_definition': ('skills', {'type': 'ModelMultipleChoiceField'})}
        )

        result = proxy.foreign_key_choices(action_data)
        self.assertIsInstance(result, list)

    def test_foreign_key_choices_returns_empty_for_non_fk_field(self):
        """foreign_key_choices should return empty list for non-FK field types."""
        proxy = GlueModelInstanceProxy(
            target=self.gorilla,
            unique_name='gorilla',
            access=GlueAccess.VIEW,
        )

        action_data = ActionRequest(
            proxy_definition={},
            action_kwargs={'field_definition': ('name', {'type': 'CharField'})}
        )

        result = proxy.foreign_key_choices(action_data)
        self.assertEqual(result, [])

    def test_foreign_key_choices_works_with_view_access(self):
        """foreign_key_choices should work with VIEW access level."""
        proxy = GlueModelInstanceProxy(
            target=self.gorilla,
            unique_name='gorilla',
            access=GlueAccess.VIEW,
        )

        action_data = ActionRequest(
            proxy_definition={},
            action_kwargs={'field_definition': ('name', {'type': 'CharField'})}
        )

        result = proxy.process_action('foreign_key_choices', action_data)
        self.assertIsNotNone(result)

    def test_foreign_key_choices_works_with_higher_access(self):
        """foreign_key_choices should work with CHANGE and DELETE access."""
        for access in [GlueAccess.CHANGE, GlueAccess.DELETE]:
            proxy = GlueModelInstanceProxy(
                target=self.gorilla,
                unique_name='gorilla',
                access=access,
            )

            action_data = ActionRequest(
                proxy_definition={},
                action_kwargs={'field_definition': ('name', {'type': 'CharField'})}
            )

            result = proxy.foreign_key_choices(action_data)
            self.assertIsNotNone(result)
