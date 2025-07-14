from django.urls import path, include

from test_project.app.home.views.page import home_view

urlpatterns = [
    path('', home_view, name='home'),
    path('django_glue/', include('django_glue.urls'), name='django_glue'),
    path('glue_form', include('test_project.app.glue_form.urls'), name='glue_form'),
    path('glue_function', include('test_project.app.glue_function.urls'), name='glue_function'),
    path('glue_model_object', include('test_project.app.glue_model_object.urls'), name='glue_model_object'),
    path('glue_queryset', include('test_project.app.glue_queryset.urls'), name='glue_queryset'),
    path('glue_view', include('test_project.app.glue_view.urls'), name='glue_view'),
]
