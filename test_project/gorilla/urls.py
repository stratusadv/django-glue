from django.urls import path

from test_project.gorilla import views

app_name = 'gorilla'

urlpatterns = [
    path('components/', views.component_view, name='components'),
    path('', views.list_view, name='list'),
    path('<int:pk>/', views.detail_view, name='detail'),
    path('<int:pk>/template/', views.detail_template_view, name='detail_template'),
    path('progressive_form/', views.progressive_form_view, name='progressive_form'),
    path('<int:pk>/arena/', views.arena_view, name='arena'),
    path('skills/', views.skills_view, name='skills'),
    path('arena/', views.random_arena_view, name='random_arena'),
]
