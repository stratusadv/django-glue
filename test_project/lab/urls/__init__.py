from django.urls import path, include

app_name = 'lab'

urlpatterns = [
    path('performance/', include('test_project.lab.urls.performance_urls'), name='performance'),
    path('connection/', include('test_project.lab.urls.connection_urls'), name='connection'),
    path('morph/', include('test_project.lab.urls.morph_urls'), name='morph'),
]
