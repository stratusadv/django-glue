from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

from tests import views

urlpatterns = [
    path("", views.TestView.as_view(), name="test"),
    path('admin/', admin.site.urls),
    path("django_glue/", include('django_glue.urls', namespace='django_glue')),
    path("no_glue/", TemplateView.as_view(template_name='no_glue.html'), name="no_glue"),
]