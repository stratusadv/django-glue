from django.urls import path, include

from app.home.views.page import home_view

urlpatterns = [
    path('', home_view, name='home'),
    path('django_glue/', include('django_glue.urls'), name='django_glue'),
]
