def connection_view(request):
    return HttpResponse("Connection view")

def logout_user_view(request):
    return HttpResponse("Logout user")

def delete_session(request):
    return HttpResponse("Delete session")

def remove_unique_name(request):
    return HttpResponse("Remove unique name")

def expire_session(request):
    return HttpResponse("Expire session")

