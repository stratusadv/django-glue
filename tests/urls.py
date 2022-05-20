from django.urls import path, include

from tests import views

urlpatterns = [
    path("", views.TestView.as_view(), name="test"),
    path("django_glue/", include('django_glue.urls', namespace='django_glue'))
]