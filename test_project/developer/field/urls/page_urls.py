from django.urls import path

from test_project.developer.field.views import page_views

app_name = 'page'
urlpatterns = [
    path('showcase/', page_views.showcase_view, name='showcase'),
    path('input-field/', page_views.input_field_view, name='input_field'),
    path('endpoint-testing/', page_views.endpoint_testing_view, name='endpoint_testing'),

]