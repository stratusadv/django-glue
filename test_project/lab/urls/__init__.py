from django.urls import path, include

app_name = 'lab'

urlpatterns = [
    path('performance/', include('test_project.lab.urls.performance_urls'), name='performance'),
]
