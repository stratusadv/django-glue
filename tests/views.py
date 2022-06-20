import logging

from django.views.generic import TemplateView

from tests.models import TestModel
from django_glue.utils import add_model_object_glue, add_model_query_set_glue


class TestView(TemplateView):
    template_name = 'test.html'

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)

        # TestModel.objects.all().delete()
        # logging.warning('Purged database of testing objects.')

        test_model_object = TestModel.objects.create(
            char='Some Characters',
            text='Alot of text goes into this text field to be tested and manipulated',
            integer=789456123,
            decimal=258.369,
        )

        # test_model_object = TestModel.objects.all().latest('id')
        logging.warning(f'Added TestModel object.')

        add_model_object_glue(self.request, 'test_model', test_model_object, 'change')
        logging.warning('Added model object glue for TestModel Object in write mode')

        add_model_query_set_glue(self.request, 'test_model_set', test_model_object, TestModel.objects.all(), 'read')
        logging.warning('Added model query set glue for TestModel Object in read mode')

        return context_data
