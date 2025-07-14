from django.urls import path, include

app_name = 'glue_function'

urlpatterns = [
    path('page', include('test_project.app.glue_function.urls.page_urls'), name='page'),
]
