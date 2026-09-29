from django.urls import path

from test_project.gorilla import views
from test_project.gorilla.components import (
    CounterCardComponent,
    CounterTallyComponent,
    LaidOutCounterCardComponent,
    ProtectedCounterCardComponent,
)

app_name = 'gorilla'

urlpatterns = [
    path('components/', views.component_view, name='components'),
    path('components/card/<int:start>/', CounterCardComponent.as_view(), name='component_card_fragment'),
    path(
        'components/protected-card/<int:start>/',
        ProtectedCounterCardComponent.as_view(),
        name='component_protected_card',
    ),
    path('components/request-card/', views.request_card_view, name='component_request_card'),
    path(
        'components/tally/',
        CounterTallyComponent.as_view(layout_template='gorilla/page/component_card_page.html'),
        name='component_tally',
    ),
    path(
        'components/card/<int:start>/page/',
        CounterCardComponent.as_view(layout_template='gorilla/page/component_card_page.html'),
        name='component_card_page',
    ),
    path(
        'components/laid-out-card/<int:start>/',
        LaidOutCounterCardComponent.as_view(),
        name='component_laid_out_card',
    ),
    path(
        'components/laid-out-card/<int:start>/alt/',
        LaidOutCounterCardComponent.as_view(
            layout_template='gorilla/page/component_card_alt_page.html'
        ),
        name='component_laid_out_card_alt',
    ),
    path('contact_formset/', views.contact_formset_view, name='contact_formset'),
    path('', views.list_view, name='list'),
    path('<int:pk>/', views.detail_view, name='detail'),
    path('<int:pk>/template/', views.detail_template_view, name='detail_template'),
    path('progressive_form/', views.progressive_form_view, name='progressive_form'),
    path('<int:pk>/arena/', views.arena_view, name='arena'),
    path('skills/', views.skills_view, name='skills'),
    path('arena/', views.random_arena_view, name='random_arena'),
]
