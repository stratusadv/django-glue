from django.urls.conf import path, include


app_name = 'glue'

urlpatterns = [
    path('page/', include('test_project.glue.urls.page_urls', namespace='page')),
]
