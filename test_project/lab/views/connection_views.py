from __future__ import annotations

from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.contrib import messages
from django.contrib.auth import logout

# def connection_view(request: HttpRequest) -> HttpResponse:
#     proxy_names = list(session.proxy_registry.keys())

#     context = {
#         'page_title': 'Test Lab',
#         'page_heading': 'Connection Management',
#         'page_subtitle': 'Inspect and manage your Glue session proxies',
#         'proxy_count': len(proxy_names),
#         'proxy_names': proxy_names,
#     }

#     return render(request, 'lab/connection/connection_page.html', context=context)


def logout_user_view(request: HttpRequest) -> HttpResponse:
    logout(request)
    messages.error(request, 'You have been logged out.')

    return HttpResponseRedirect('/')


def delete_session(request: HttpRequest) -> HttpResponse:
    request.session.flush()
    messages.error(request, 'Session has been deleted.')

    return HttpResponseRedirect('/')


# def remove_unique_name(request: HttpRequest) -> HttpResponse:
#     session = GlueSession(request)

#     if request.method == 'POST':
#         proxy_name = request.POST.get('proxy_name', '')

#         if proxy_name:
#             session.proxy_registry.pop(proxy_name, None)
#             session._set_modified()
#             messages.error(request, f"Proxy '{proxy_name}' has been removed.")

#         return HttpResponseRedirect('/')

#     proxy_names = list(session.proxy_registry.keys())

#     context = {
#         'page_title': 'Test Lab',
#         'page_heading': 'Remove Proxy',
#         'page_subtitle': 'Select a proxy to remove from the current session',
#         'proxy_names': proxy_names,
#     }

#     return render(request, 'lab/connection/remove_proxy_page.html', context=context)


# def expire_session(request: HttpRequest) -> HttpResponse:
#     session = GlueSession(request)

#     session.proxy_registry.clear()
#     session._set_modified()
#     messages.error(request, 'All proxies have been expired.')

#     return HttpResponseRedirect('/')
