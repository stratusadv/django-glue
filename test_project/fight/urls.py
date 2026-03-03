from django.urls import path

from test_project.fight import views

app_name = 'fight'

urlpatterns = [
    path('', views.list_view, name='list'),
    path('schedule/', views.schedule_view, name='schedule'),
]
