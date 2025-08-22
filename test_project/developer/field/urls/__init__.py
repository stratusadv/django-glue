from django.urls.conf import path, include


app_name = 'fields'

urlpatterns = [
    path('page/', include('test_project.developer.field.urls.page_urls', namespace='page')),
]
