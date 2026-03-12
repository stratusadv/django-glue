from django.urls import path

from test_project.comments import views

app_name = 'comments'

urlpatterns = [
    path('<int:content_type_id>/<int:object_id>/', views.comments_partial_view, name='partial'),
]
