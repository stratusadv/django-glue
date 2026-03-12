from django.urls import path

from test_project.gorilla import views

app_name = 'gorilla'

urlpatterns = [
    path('', views.list_view, name='list'),
    path('<int:pk>/', views.detail_view, name='detail'),
    path('skills/', views.skills_view, name='skills'),
]
