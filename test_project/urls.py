from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from django_glue import django_glue_urls

urlpatterns = [
    path('', include('test_project.gorilla.urls')),
    path('fight/', include('test_project.fight.urls')),
    path('comments/', include('test_project.comments.urls')),
    path('lab/', include('test_project.lab.urls')),
    path('admin/', admin.site.urls),
]

urlpatterns += django_glue_urls()

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
