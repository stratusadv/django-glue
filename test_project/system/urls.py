from django.urls import path, include

from test_project.app.home.views.page import home_view

urlpatterns = [
    path('', home_view, name='home'),
    path('django_glue/', include('django_glue.urls'), name='django_glue'),
    path('gorilla/', include('test_project.app.gorilla.urls', namespace='gorilla'), ),
    path('developer/', include('test_project.developer.urls', namespace='glue_forms')),
    path('theme/', include('django_spire.theme.urls', namespace='theme')),
]
