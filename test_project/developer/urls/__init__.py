from django.urls.conf import path, include


app_name = 'developer'

urlpatterns = [
    path('page/', include('test_project.developer.urls.page_urls', namespace='page')),
    path('form/', include('test_project.developer.form.urls', namespace='form')),
    path('field/', include('test_project.developer.field.urls', namespace='field')),
]
