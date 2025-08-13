from __future__ import annotations

from typing_extensions import TYPE_CHECKING

from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse

if TYPE_CHECKING:
    from django.core.handlers.wsgi import WSGIRequest


def main_page_view(request: WSGIRequest) -> TemplateResponse:
    """Main page view that links to the session data view."""
    return TemplateResponse(
        request=request,
        template='glue/page/main_page.html',
        context={}
    )


def session_data_view(request: WSGIRequest) -> TemplateResponse:
    """View that displays session data."""
    
    # Add some test data to the session if it's empty
    if not request.session.items():
        request.session['test_key'] = 'test_value'
        request.session['user_info'] = {
            'last_visit': '2025-08-12 18:09',
            'page_views': 42,
            'preferences': {
                'theme': 'dark',
                'language': 'en-US'
            }
        }
    
    return TemplateResponse(
        request=request,
        context={'session_data': request.session},
        template='glue/page/session_data.html'
    )
