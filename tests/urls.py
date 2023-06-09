from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

from tests import views

urlpatterns = [
    path("", views.TestView.as_view(), name="test_glue"),
    path("other/", views.OtherView.as_view(), name="other_glue"),
    path("no_glue/", TemplateView.as_view(template_name='page/no_glue_page.html'), name="no_glue"),
    path("django_glue/", include('django_glue.urls', namespace='django_glue')),
]

urlpatterns += [
    path('admin/', admin.site.urls),
]