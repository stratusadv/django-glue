from tests.test_base import BaseTestCase


class TestDjangoGlue(BaseTestCase):
    def test_import(self):
        try:
            import django_glue as dp

            self.assertTrue(True)
        except ImportError:
            self.assertTrue(False)

    def test_shortcuts_import(self):
        try:
            from django_glue.shortcuts import glue_template, glue_model_object, glue_query_set, glue_function

            self.assertTrue(True)
        except ImportError:
            self.assertTrue(False)

