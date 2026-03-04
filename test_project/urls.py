from django.contrib import admin
from django.urls import path, include

from django_glue import django_glue_urls

urlpatterns = [
    path('', include('test_project.gorilla.urls')),
    path('fight/', include('test_project.fight.urls')),
    path('lab/', include('test_project.lab.urls')),
    path('admin/', admin.site.urls),
]

urlpatterns += django_glue_urls()
