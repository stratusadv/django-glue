from django.contrib import admin
from django.urls import path, include

from tests import views

urlpatterns = [
    path("", views.TestView.as_view(), name="test"),
    path('admin/', admin.site.urls),
    path("glue/", include('django_glue.urls', namespace='django_glue'))
]