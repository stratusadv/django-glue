from django.urls.conf import path, include


app_name = 'form'

urlpatterns = [
    path('page/', include('test_project.developer.form.urls.page_urls', namespace='page')),
    path('fields/', include('test_project.developer.field.urls', namespace='fields'))

]
