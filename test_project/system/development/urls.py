from django.urls import path, include

from test_project.app.home.views.page import home_view

urlpatterns = [
    path('', home_view, name='home'),
    path('django_glue/', include('django_glue.urls'), name='django_glue'),
    path('glue_model_object', include('test_project.app.glue_model_object.urls'), name='glue_model_object'),
]
