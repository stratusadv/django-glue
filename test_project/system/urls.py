from django.urls import path, include

from test_project.app.home.views.page import home_view

urlpatterns = [
    path('', home_view, name='home'),
    path('django_glue/', include('django_glue.urls'), name='django_glue'),
    path('gorilla/', include('test_project.app.gorilla.urls', namespace='gorilla'), ),
    path('glue/forms/', include('test_project.glue.form.urls', namespace='glue_forms')),
    path('glue/', include('test_project.glue.urls', namespace='glue')),
    path('theme/', include('django_spire.theme.urls', namespace='theme')),
]
