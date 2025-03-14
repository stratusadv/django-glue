from django.template.response import TemplateResponse


def home_view(request):
    return TemplateResponse(
        request,
        template='home/page/home_page.html'
    )
