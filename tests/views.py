import logging

from django.template.response import TemplateResponse
from django.views.generic import TemplateView

from tests.models import TestModel
from tests.utils import generate_randomized_test_model, generate_big_test_model
from django_glue.glue import add_glue


class ModelObjectView(TemplateView):
    template_name = 'page/model_object_page.html'

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)

        test_model_object = generate_randomized_test_model()

        add_glue(self.request, 'test_model_1', test_model_object, 'delete', exclude=('birth_date', 'anniversary_datetime'), methods=['is_lighter_than', 'get_full_name'])
        add_glue(self.request, 'test_model_2', test_model_object, 'change', exclude=('birth_date', 'anniversary_datetime'))
        add_glue(self.request, 'test_model_3', test_model_object, 'delete', exclude=('birth_date', 'anniversary_datetime'))
        add_glue(self.request, 'test_model_4', test_model_object, 'change', exclude=('birth_date', 'anniversary_datetime'))

        big_test_model_object = generate_big_test_model()

        return context_data


class QuerySetView(TemplateView):
    template_name = 'page/query_set_page.html'

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)

        add_glue(self.request, 'test_query_1', TestModel.objects.filter(id__gte=1).filter(id__lte=10000), 'delete', exclude=('anniversary_datetime',), methods=['is_lighter_than', 'get_full_name'])
        add_glue(self.request, 'test_query_2', TestModel.objects.filter(id__gte=1).filter(id__lte=10000), 'add', exclude=('birth_date', 'anniversary_datetime'))
        add_glue(self.request, 'test_query_3', TestModel.objects.filter(id__gte=1).filter(id__lte=10000), 'change', exclude=('birth_date', 'anniversary_datetime'))

        context_data['model_object_id'] = TestModel.objects.filter(id__gte=1).filter(id__lte=10000).first().id
        return context_data


def query_set_list_view(request):
    add_glue(request, 'test_query_1', TestModel.objects.all(), 'delete')
    return TemplateResponse(
        request,
        template='page/query_set_list_page.html'
    )


class OtherView(TemplateView):
    template_name = 'page/other_glue_page.html'
    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)

        other_test_model_object = generate_randomized_test_model()

        logging.warning(f'Added Other TestModel object.')

        add_glue(self.request, 'other_test_model_1', other_test_model_object, 'change', exclude=('birth_date', 'anniversary_datetime',))

        logging.warning('Added model object glue for Other TestModel Object in write mode')

        return context_data


def benchmark_view(request):
    from time import time
    import random
    import string

    benchmarks = {}

    test_model_object = generate_randomized_test_model()

    def generate_random_string(length):
        return ''.join(random.choice(string.ascii_letters) for _ in range(length))

    start = time()
    stop = time()

    benchmarks['No Glue'] = stop - start

    random_strings = [generate_random_string(5) for _ in range(1)]

    start = time()
    for unique_name in random_strings:
        add_glue(request, unique_name, test_model_object, 'delete', exclude=('birth_date', 'anniversary_datetime'), methods=['is_lighter_than', 'get_full_name'])
    stop = time()

    benchmarks['1 Glue'] = stop - start

    random_strings = [generate_random_string(5) for _ in range(10)]

    start = time()
    for unique_name in random_strings:
        add_glue(request, unique_name, test_model_object, 'delete', exclude=('birth_date', 'anniversary_datetime'), methods=['is_lighter_than', 'get_full_name'])
    stop = time()

    benchmarks['10 Glue'] = stop - start

    random_strings = [generate_random_string(5) for _ in range(100)]

    start = time()
    for unique_name in random_strings:
        add_glue(request, unique_name, test_model_object, 'delete', exclude=('birth_date', 'anniversary_datetime'), methods=['is_lighter_than', 'get_full_name'])
    stop = time()

    benchmarks['100 Glue'] = stop - start

    random_strings = [generate_random_string(5) for _ in range(1000)]

    start = time()
    for unique_name in random_strings:
        add_glue(request, unique_name, test_model_object, 'delete', exclude=('birth_date', 'anniversary_datetime'), methods=['is_lighter_than', 'get_full_name'])
    stop = time()

    benchmarks['1000 Glue'] = stop - start

    return TemplateResponse(request, 'page/benchmark_page.html', {'benchmarks': benchmarks})


def view_view(request):
    return TemplateResponse(request, 'page/view_page.html')


def view_card_view(request):
    test_model_object = generate_randomized_test_model()

    add_glue(request, 'test_model_view_card', test_model_object, 'delete', exclude=('birth_date', 'anniversary_datetime'),
             methods=['is_lighter_than', 'get_full_name'])

    return TemplateResponse(request, 'card/view_card.html')

def template_view(request):
    add_glue(request, 'button_1', 'element/button_element.html')

    return TemplateResponse(request, 'page/template_page.html')