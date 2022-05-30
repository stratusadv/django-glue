import logging

from django.views.generic import TemplateView

from tests.models import TestModel
from django_glue.models import FieldGlue, ObjectGlue
from django_glue.utils import add_glue


class TestView(TemplateView):
    template_name = 'test.html'

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)

        TestModel.objects.all().delete()
        FieldGlue.objects.all().delete()
        ObjectGlue.objects.all().delete()

        logging.warning('Purged database of testing objects.')

        test_model = TestModel.objects.create(
            char='Some Characters',
            text='Alot of text goes into this text field to be tested and manipulated',
            integer=789456123,
            decimal=258.369,
        )

        # test_model = TestModel.objects.all().latest('id')

        logging.warning(f'Added TestModel object.')

        add_glue(test_model, 'write', 'text')
        logging.warning('Added model field glue for TestModel Object in write mode')

        add_glue(test_model, 'write')
        logging.warning('Added model object glue for TestModel Object in write mode')

        return context_data
