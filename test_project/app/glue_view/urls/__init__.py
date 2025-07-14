from django.urls import path, include

app_name = 'glue_view'

urlpatterns = [
path('page', include('test_project.app.glue_view.urls.page_urls'), name='page'),
]
