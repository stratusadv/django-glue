from django.urls.conf import path, include


app_name = 'gorilla'

urlpatterns = [
    path('page/', include('test_project.app.gorilla.urls.page_urls', namespace='page')),
    path('form/', include('test_project.app.gorilla.urls.form_urls', namespace='form')),
]
