"""
Tests for Django Glue GlueAccess permission system.
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.settings')
django.setup()

from django.test import TestCase

from django_glue.access import GlueAccess


class GlueAccessEnumTestCase(TestCase):
    """Tests for GlueAccess enum values and string representation."""

    def test_view_value(self):
        """VIEW should have value 'view'."""
        self.assertEqual(GlueAccess.VIEW.value, 'view')

    def test_add_value(self):
        """ADD should have value 'add'."""
        self.assertEqual(GlueAccess.ADD.value, 'add')

    def test_change_value(self):
        """CHANGE should have value 'change'."""
        self.assertEqual(GlueAccess.CHANGE.value, 'change')

    def test_delete_value(self):
        """DELETE should have value 'delete'."""
        self.assertEqual(GlueAccess.DELETE.value, 'delete')

    def test_str_returns_value(self):
        """__str__ should return the enum value."""
        self.assertEqual(str(GlueAccess.VIEW), 'view')
        self.assertEqual(str(GlueAccess.ADD), 'add')
        self.assertEqual(str(GlueAccess.CHANGE), 'change')
        self.assertEqual(str(GlueAccess.DELETE), 'delete')

    def test_is_string_subclass(self):
        """GlueAccess should be a string subclass for easy comparison."""
        self.assertIsInstance(GlueAccess.VIEW, str)
        self.assertEqual(GlueAccess.VIEW, 'view')


class GlueAccessHasAccessTestCase(TestCase):
    """Tests for GlueAccess.has_access() permission hierarchy."""

    # VIEW access tests
    def test_view_has_access_to_view(self):
        """VIEW access should allow VIEW operations."""
        self.assertTrue(GlueAccess.VIEW.has_access(GlueAccess.VIEW))

    def test_view_does_not_have_access_to_change(self):
        """VIEW access should deny CHANGE operations."""
        self.assertFalse(GlueAccess.VIEW.has_access(GlueAccess.CHANGE))

    def test_view_does_not_have_access_to_delete(self):
        """VIEW access should deny DELETE operations."""
        self.assertFalse(GlueAccess.VIEW.has_access(GlueAccess.DELETE))

    def test_view_does_not_have_access_to_add(self):
        """VIEW access should deny ADD operations."""
        self.assertFalse(GlueAccess.VIEW.has_access(GlueAccess.ADD))

    # ADD access tests
    def test_add_has_access_to_view(self):
        """ADD access should allow VIEW operations (cascading)."""
        self.assertTrue(GlueAccess.ADD.has_access(GlueAccess.VIEW))

    def test_add_has_access_to_add(self):
        """ADD access should allow ADD operations."""
        self.assertTrue(GlueAccess.ADD.has_access(GlueAccess.ADD))

    def test_add_does_not_have_access_to_change(self):
        """ADD access should deny CHANGE operations."""
        self.assertFalse(GlueAccess.ADD.has_access(GlueAccess.CHANGE))

    def test_add_does_not_have_access_to_delete(self):
        """ADD access should deny DELETE operations."""
        self.assertFalse(GlueAccess.ADD.has_access(GlueAccess.DELETE))

    # CHANGE access tests
    def test_change_has_access_to_view(self):
        """CHANGE access should allow VIEW operations (cascading)."""
        self.assertTrue(GlueAccess.CHANGE.has_access(GlueAccess.VIEW))

    def test_change_has_access_to_add(self):
        """CHANGE access should allow ADD operations (cascading)."""
        self.assertTrue(GlueAccess.CHANGE.has_access(GlueAccess.ADD))

    def test_change_has_access_to_change(self):
        """CHANGE access should allow CHANGE operations."""
        self.assertTrue(GlueAccess.CHANGE.has_access(GlueAccess.CHANGE))

    def test_change_does_not_have_access_to_delete(self):
        """CHANGE access should deny DELETE operations."""
        self.assertFalse(GlueAccess.CHANGE.has_access(GlueAccess.DELETE))

    # DELETE access tests
    def test_delete_has_access_to_view(self):
        """DELETE access should allow VIEW operations (cascading)."""
        self.assertTrue(GlueAccess.DELETE.has_access(GlueAccess.VIEW))

    def test_delete_has_access_to_add(self):
        """DELETE access should allow ADD operations (cascading)."""
        self.assertTrue(GlueAccess.DELETE.has_access(GlueAccess.ADD))

    def test_delete_has_access_to_change(self):
        """DELETE access should allow CHANGE operations (cascading)."""
        self.assertTrue(GlueAccess.DELETE.has_access(GlueAccess.CHANGE))

    def test_delete_has_access_to_delete(self):
        """DELETE access should allow DELETE operations."""
        self.assertTrue(GlueAccess.DELETE.has_access(GlueAccess.DELETE))


class GlueAccessHierarchyTestCase(TestCase):
    """Tests for the overall permission hierarchy structure."""

    def test_permission_order(self):
        """Permissions should be ordered VIEW < ADD < CHANGE < DELETE."""
        access_tuple = tuple(GlueAccess.__members__.values())

        self.assertEqual(access_tuple[0], GlueAccess.VIEW)
        self.assertEqual(access_tuple[1], GlueAccess.ADD)
        self.assertEqual(access_tuple[2], GlueAccess.CHANGE)
        self.assertEqual(access_tuple[3], GlueAccess.DELETE)

    def test_higher_access_includes_all_lower(self):
        """Higher access levels should include all lower access levels."""
        # DELETE includes everything
        self.assertTrue(GlueAccess.DELETE.has_access(GlueAccess.VIEW))
        self.assertTrue(GlueAccess.DELETE.has_access(GlueAccess.ADD))
        self.assertTrue(GlueAccess.DELETE.has_access(GlueAccess.CHANGE))
        self.assertTrue(GlueAccess.DELETE.has_access(GlueAccess.DELETE))

        # CHANGE includes VIEW and ADD
        self.assertTrue(GlueAccess.CHANGE.has_access(GlueAccess.VIEW))
        self.assertTrue(GlueAccess.CHANGE.has_access(GlueAccess.ADD))
        self.assertTrue(GlueAccess.CHANGE.has_access(GlueAccess.CHANGE))

        # ADD includes VIEW
        self.assertTrue(GlueAccess.ADD.has_access(GlueAccess.VIEW))
        self.assertTrue(GlueAccess.ADD.has_access(GlueAccess.ADD))

        # VIEW only includes VIEW
        self.assertTrue(GlueAccess.VIEW.has_access(GlueAccess.VIEW))
