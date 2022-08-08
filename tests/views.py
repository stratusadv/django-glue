import logging, random

from django.views.generic import TemplateView

from tests.models import TestModel
from django_glue.utils import add_glue

FIRST_NAME_TUPLE = (
    'Nathan',
    'Ted',
    'Janet',
    'Fred',
    'Jane',
    'Johnny',
    'Robert',
)

LAST_NAME_TUPLE = (
    'Wilson',
    'Hansen',
    'Waldern',
    'Smith',
    'Doe',
    'Johnson',
    'Mancal',
)

DESCRIPTION_WORD_TUPLE = (
    'has',
    'a',
    'dog',
    'started',
    'cat',
    'fly',
    'when',
    'handy',
    'taco',
    'stupid',
    'are'
    'there',
    'I',
    'you',
    'awesome',
    'cool',
    'ugly',
    'she',
    'want',
    'need',
    'have',
    'finished',
    'fast',
    'when',
    'loves cars',
    'boring',
    'artsy',
    'wood carving'
)


class TestView(TemplateView):
    template_name = 'test.html'

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)

        # TestModel.objects.all().delete()
        # logging.warning('Purged database of testing objects.')

        new_description = ''
        for x in range(10):
            new_description += f'{DESCRIPTION_WORD_TUPLE[random.randint(0, (len(DESCRIPTION_WORD_TUPLE) - 1))]} '

        test_model_object = TestModel.objects.create(
            first_name=FIRST_NAME_TUPLE[random.randint(0, (len(FIRST_NAME_TUPLE) - 1))],
            last_name=LAST_NAME_TUPLE[random.randint(0, (len(LAST_NAME_TUPLE) - 1))],
            description=new_description,
            favorite_number=random.randint(0, 999),
            weight_lbs=round(random.uniform(80.0, 400.0), 1),
        )

        exclude_test_model = TestModel.objects.all().order_by('-id')[:5]
        TestModel.objects.exclude(pk__in=exclude_test_model).delete()

        # test_model_object = TestModel.objects.all().latest('id')
        logging.warning(f'Added TestModel object.')

        add_glue(self.request, 'test_model_live', test_model_object, 'change', exclude=('birth_date', 'anniversary_datetime'))
        add_glue(self.request, 'test_model_form', test_model_object, 'change', exclude=('birth_date', 'anniversary_datetime'))
        logging.warning('Added model object glue for TestModel Object in write mode')

        add_glue(self.request, 'test_model_set', TestModel.objects.filter(id__gte=1).filter(id__lte=10000), 'read')
        logging.warning('Added model query set glue for TestModel Object in read mode')

        return context_data
