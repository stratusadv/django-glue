from django.urls import path

from tests import views

urlpatterns = [
    path("", views.TestView.as_view(), name="test"),
]