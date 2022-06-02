import logging

from django.views.generic import TemplateView

from tests.models import TestModel
from django_glue.utils import add_model_object_glue, clean_glue_session


class TestView(TemplateView):
    template_name = 'test.html'

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)

        TestModel.objects.all().delete()

        logging.warning('Purged database of testing objects.')

        test_model_object = TestModel.objects.create(
            char='Some Characters',
            text='Alot of text goes into this text field to be tested and manipulated',
            integer=789456123,
            decimal=258.369,
        )

        # test_model_object = TestModel.objects.all().latest('id')

        logging.warning(f'Added TestModel object.')

        # clean_glue_session(self.request)
        # logging.warning(f'Cleanup Django Glue Session Dictionary')

        add_model_object_glue(self.request, 'test_glue', test_model_object, 'write')
        logging.warning('Added model field glue for TestModel Object in write mode')

        # add_model_object_glue(self.request, test_model_object, 'write')
        # logging.warning('Added model object glue for TestModel Object in write mode')

        return context_data
