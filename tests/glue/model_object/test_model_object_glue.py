from tests.test_base import BaseTestCase

import django_glue as dg


class TestModelObjectGlue(BaseTestCase):
    def test_glue(self):
        try:
            dg.glue_model_object(
                self.request,
                'person_model_object',
                self.gorilla_model_object
            )

            self.assertTrue(True)
        except ImportError:
            self.assertTrue(False)

