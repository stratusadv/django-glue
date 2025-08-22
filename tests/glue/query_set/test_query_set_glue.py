from tests.test_base import BaseTestCase

import django_glue as dg


class TestQuerySetGlue(BaseTestCase):
    def test_glue(self):
        try:
            dg.glue_query_set(
                self.request,
                'person_query_set',
                self.gorilla_model_class.objects.all()
            )

            self.assertTrue(True)
        except ImportError:
            self.assertTrue(False)

