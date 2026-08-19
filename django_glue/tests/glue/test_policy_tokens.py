from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from django_glue.access import GlueAccess
from django_glue.exceptions import GlueExpiredPolicyError, GlueInvalidPolicyError
from django_glue.glue.policy import GluePolicy


class GluePolicyTokenTestCase(TestCase):
    def policy(self, **overrides) -> GluePolicy:
        return GluePolicy.new_signed_policy({
            'session_id': 'session-1',
            'request_user_id': None,
            'name': 'project_form',
            'namespace': 'form',
            'identity': {
                'form_class_path': 'app.project.forms.ProjectForm',
                'initial': {'estimated_hours': 0.0},
            },
            'access': GlueAccess.CHANGE,
            'attributes': ['load_state', 'save'],
            **overrides,
        })

    def test_token_round_trip_restores_policy(self):
        policy = self.policy()

        restored = GluePolicy.from_token(policy.token)

        self.assertEqual(restored.name, policy.name)
        self.assertEqual(restored.identity, policy.identity)
        self.assertEqual(restored.access, policy.access)
        self.assertEqual(restored.attributes, policy.attributes)

    def test_tampered_token_is_rejected(self):
        policy = self.policy()

        with self.assertRaises(GlueInvalidPolicyError):
            GluePolicy.from_token(f'{policy.token}x')

    @override_settings(DJANGO_GLUE_PROXY_POLICY_MAX_AGE_SECONDS=60)
    def test_expired_token_is_rejected(self):
        issued_at = timezone.now() - timedelta(minutes=2)
        with patch('django_glue.glue.policy.timezone.now', return_value=issued_at):
            policy = self.policy()

        with self.assertRaises(GlueExpiredPolicyError):
            GluePolicy.from_token(policy.token)

    def test_visible_policy_changes_do_not_change_token_authority(self):
        policy = self.policy()
        client_policy = policy.model_dump()
        client_policy['name'] = 'attacker_controlled_name'
        client_policy['access'] = GlueAccess.DELETE

        restored = GluePolicy.from_token(client_policy['token'])

        self.assertEqual(restored.name, 'project_form')
        self.assertEqual(restored.access, GlueAccess.CHANGE)

    def test_browser_numeric_normalization_does_not_change_token_identity(self):
        policy = self.policy()
        client_policy = policy.model_dump()

        # JavaScript JSON.stringify emits integral 0.0 as 0. The visible policy may
        # therefore change during a browser round trip, but the opaque token does not.
        client_policy['identity']['initial']['estimated_hours'] = 0

        restored = GluePolicy.from_token(client_policy['token'])
        estimated_hours = restored.identity['initial']['estimated_hours']

        self.assertIsInstance(estimated_hours, float)
        self.assertEqual(estimated_hours, 0.0)

    def test_nested_policy_has_its_own_token(self):
        child = self.policy(name='project_form.child')
        parent = self.policy(attributes=['load_state', child])

        restored_parent = GluePolicy.from_token(parent.token)
        restored_child = restored_parent.attributes[1]

        self.assertIsInstance(restored_child, GluePolicy)
        self.assertTrue(restored_child.token)
        self.assertEqual(
            GluePolicy.from_token(restored_child.token).name,
            'project_form.child',
        )
