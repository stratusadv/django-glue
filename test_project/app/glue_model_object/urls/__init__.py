from django.urls import path, include

app_name = 'glue_model_object'

urlpatterns = [
    path('page', include('test_project.app.glue_model_object.urls.page_urls'), name='page'),
]
