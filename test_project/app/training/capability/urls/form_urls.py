from django.urls import path

from test_project.app.training.capability.views import form_views

app_name = 'form'
urlpatterns = [
    path('<int:pk>/delete/form/', form_views.delete_view, name='delete'),
    path('<int:pk>/delete/form/modal/', form_views.delete_form_modal_view, name='delete_form_modal'),
    path('<int:pk>/form/content/', form_views.form_content_modal_view, name='form_modal_content'),
    path('<int:pk>/form/', form_views.form_view, name='form'),
]