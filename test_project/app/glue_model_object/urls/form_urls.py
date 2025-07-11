from django.urls import path

from test_project.app.glue_model_object.views import form_views

app_name = 'form'

urlpatterns = [
    path('create/',
         form_views.form_view,
         name='create'),

    path('<int:pk>/update/',
         form_views.form_view,
         name='update'),
]
