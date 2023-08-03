from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

from tests import views

urlpatterns = [
    path("", views.ModelObjectView.as_view(), name="model_object"),
    path("big_model", views.big_model_object_view, name="big_model"),
    path("query_set/", views.QuerySetView.as_view(), name="query_set"),
    path("query_set/list/", views.query_set_list_view, name="query_set_list"),
    path("other/", views.OtherView.as_view(), name="other_glue"),
    path("no_glue/", TemplateView.as_view(template_name='page/no_glue_page.html'), name="no_glue"),
    path("benchmark/", views.benchmark_view, name="benchmark"),
    path("django_glue/", include('django_glue.urls', namespace='django_glue')),
    path("template/", views.template_view, name="template"),
    path("view/", views.view_view, name="view"),
    path("view/card/", views.view_card_view, name="view_card"),
]

urlpatterns += [
    path('admin/', admin.site.urls),
]