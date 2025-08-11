from django.urls.conf import path, include


app_name = 'form'

urlpatterns = [
    path('page/', include('test_project.glue.form.urls.page_urls', namespace='page')),
    path('fields/', include('test_project.glue.form.fields.urls', namespace='fields'))

]
