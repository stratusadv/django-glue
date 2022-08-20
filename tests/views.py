import logging, random

from django.views.generic import TemplateView

from tests.models import TestModel
from django_glue.utils import add_glue

FIRST_NAME_TUPLE = (
    'Fred',
    'Jane',
    'Janet',
    'Johnny',
    'Nathan',
    'Robert',
    'Ted',
)

LAST_NAME_TUPLE = (
    'Doe',
    'Hansen',
    'Johnson',
    'Mancal',
    'Smith',
    'Waldern',
    'Wilson',
)

DESCRIPTION_WORD_TUPLE = (
    'I',
    'a',
    'are'
    'artsy',
    'awesome',
    'boring',
    'can',
    'cat',
    'cool',
    'dog',
    'fast',
    'finished',
    'fly',
    'handy',
    'has',
    'has',
    'have',
    'it',
    'loves cars',
    'need',
    'she',
    'started',
    'stupid',
    'taco',
    'there',
    'to',
    'ugly',
    'want',
    'when',
    'when',
    'wood carving'
    'you',
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

        add_glue(self.request, 'test_model_1', test_model_object, 'change', exclude=('birth_date', 'anniversary_datetime'))
        add_glue(self.request, 'test_model_2', test_model_object, 'change', exclude=('birth_date', 'anniversary_datetime'))
        add_glue(self.request, 'test_model_3', test_model_object, 'delete', exclude=('birth_date', 'anniversary_datetime'))
        add_glue(self.request, 'test_model_4', test_model_object, 'change', exclude=('birth_date', 'anniversary_datetime'))
        logging.warning('Added model object glue for TestModel Object in write mode')

        add_glue(self.request, 'test_query_1', TestModel.objects.filter(id__gte=1).filter(id__lte=10000), 'change', exclude=('birth_date', 'anniversary_datetime'))
        add_glue(self.request, 'test_query_2', TestModel.objects.filter(id__gte=1).filter(id__lte=10000), 'add', exclude=('birth_date', 'anniversary_datetime'))
        add_glue(self.request, 'test_query_3', TestModel.objects.filter(id__gte=1).filter(id__lte=10000), 'delete', exclude=('birth_date', 'anniversary_datetime'))
        logging.warning('Added model query set glue for TestModel Object in read mode')

        return context_data
