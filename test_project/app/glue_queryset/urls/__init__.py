from django.urls import path, include

app_name = 'glue_queryset'

urlpatterns = [
    path('page', include('test_project.app.glue_queryset.urls.page_urls'), name='page'),
]
