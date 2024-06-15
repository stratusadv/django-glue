import json
import logging

from django.shortcuts import render
from django.template.response import TemplateResponse
from django.views.generic import TemplateView

from tests.models import TestModel, BigTestModel, UuidTestModel
from tests.processors import get_complex_form_processor
from tests.utils import generate_randomized_test_model, generate_big_test_model
from tests.context_data import django_glue_context_data

from django_glue.glue import glue_model, glue_query_set, glue_template, glue_function


def big_model_object_view(request):
    big_model = generate_big_test_model()
    glue_model(request, 'big_model', big_model, 'delete', fields=('foreign_key',))
    glue_query_set(request, 'big_model_query', BigTestModel.objects.all(), 'delete', fields=('foreign_key',))

    return TemplateResponse(request, template='page/big_model_object_page.html')


class ModelObjectView(TemplateView):
    template_name = 'page/model_object_page.html'

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        context_data.update(django_glue_context_data(self.request))

        test_model_object = generate_randomized_test_model()

        glue_model(self.request, 'test_model_1', test_model_object, 'delete', exclude=('birth_date', 'anniversary_datetime'), methods=['is_lighter_than', 'get_full_name'])
        # glue_model(self.request, 'test_model_2', test_model_object, 'change', exclude=('birth_date', 'anniversary_datetime'))
        # glue_model(self.request, 'test_model_3', test_model_object, 'delete', exclude=('birth_date', 'anniversary_datetime'))
        # glue_model(self.request, 'test_model_4', test_model_object, 'change', exclude=('birth_date', 'anniversary_datetime'))

        big_test_model_object = generate_big_test_model()

        return context_data


class QuerySetView(TemplateView):
    template_name = 'page/query_set_page.html'

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)

        context_data.update(django_glue_context_data(self.request))

        glue_query_set(self.request, 'test_query_1', TestModel.objects.filter(id__gte=1).filter(id__lte=10000), 'delete', exclude=('anniversary_datetime', 'birth_date'), methods=['is_lighter_than', 'get_full_name'])
        glue_query_set(self.request, 'test_query_3', TestModel.objects.filter(id__gte=1).filter(id__lte=10000), 'change', exclude=('birth_date', 'anniversary_datetime'))

        context_data['model_object_id'] = TestModel.objects.filter(id__gte=1).filter(id__lte=10000).first().id
        return context_data


def query_set_list_view(request):
    glue_query_set(request, 'test_query_1', TestModel.objects.all(), 'delete')
    return TemplateResponse(
        request,
        template='page/query_set_list_page.html'
    )


class OtherView(TemplateView):
    template_name = 'page/other_glue_page.html'

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)

        context_data.update(django_glue_context_data(self.request))

        other_test_model_object = generate_randomized_test_model()

        logging.warning(f'Added Other TestModel object.')

        glue_model(self.request, 'other_test_model_1', other_test_model_object, 'change', exclude=('birth_date', 'anniversary_datetime',))

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
        glue_model(request, unique_name, test_model_object, 'delete', exclude=('birth_date', 'anniversary_datetime'), methods=['is_lighter_than', 'get_full_name'])
    stop = time()

    benchmarks['1 Glue'] = stop - start

    random_strings = [generate_random_string(5) for _ in range(10)]

    start = time()
    for unique_name in random_strings:
        glue_model(request, unique_name, test_model_object, 'delete', exclude=('birth_date', 'anniversary_datetime'), methods=['is_lighter_than', 'get_full_name'])
    stop = time()

    benchmarks['10 Glue'] = stop - start

    random_strings = [generate_random_string(5) for _ in range(100)]

    start = time()
    for unique_name in random_strings:
        glue_model(request, unique_name, test_model_object, 'delete', exclude=('birth_date', 'anniversary_datetime'), methods=['is_lighter_than', 'get_full_name'])
    stop = time()

    benchmarks['100 Glue'] = stop - start

    random_strings = [generate_random_string(5) for _ in range(1000)]

    start = time()
    for unique_name in random_strings:
        glue_model(request, unique_name, test_model_object, 'delete', exclude=('birth_date', 'anniversary_datetime'), methods=['is_lighter_than', 'get_full_name'])
    stop = time()

    benchmarks['1000 Glue'] = stop - start

    return TemplateResponse(request, 'page/benchmark_page.html', {'benchmarks': benchmarks})


def view_view(request):
    return TemplateResponse(request, 'page/view_page.html')


def view_card_view(request):
    test_model_object = generate_randomized_test_model()

    glue_model(
        request=request,
        unique_name='test_model_view_card',
        target=test_model_object,
        access='delete',
        exclude=('birth_date', 'anniversary_datetime'),
        methods=['is_lighter_than', 'get_full_name']
    )

    return TemplateResponse(request, 'card/view_card.html')


def template_view(request):
    glue_template(request, 'button_1', 'element/button_element.html')

    return TemplateResponse(request, 'page/template_page.html')


def function_view(request):
    glue_function(request, 'function_1', 'tests.utils.test_glue_function')
    return TemplateResponse(request, 'page/function_page.html')


def form_field_view(request):
    person = generate_randomized_test_model()
    glue_model(request, 'person', person)
    return TemplateResponse(request, 'page/form_fields_page.html')


def complex_form_view(request):
    LOCATION_CHOICES = [
        {'key': 'NYC', 'value': 'New York'},
        {'key': 'CHI', 'value': 'Chicago'},
    ]

    context_data = {
        'location_choices': LOCATION_CHOICES,
    }

    glue_template(request, 'new_york_element', 'complex_form/element/new_york_element.html')
    glue_template(request, 'chicago_element', 'complex_form/element/chicago_element.html')

    if request.POST:
        form = get_complex_form_processor(request.POST)
        if form.is_valid():
            print('Valid!')
        else:
            context_data['initial'] = json.dumps(request.POST)
            print(form.errors)

    return render(request, 'complex_form/page/complex_form_page.html', context_data)


def complex_model_form_view(request):
    glue_query_set(request, 'test_queryset', TestModel.objects.all(), 'delete')
    context_data = {}

    return render(request, 'complex_form/page/complex_model_form_page.html', context_data)


def uuid_model_view(request):
    uuid_title_model = UuidTestModel.objects.create(title='New Title of Function')
    glue_model(request, 'uuid_title_model', uuid_title_model)
    return TemplateResponse(request, 'page/uuid_model_page.html')
