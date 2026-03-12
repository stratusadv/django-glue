from django.http import HttpRequest
from django.shortcuts import render
from django.contrib.contenttypes.models import ContentType

from django_glue import Glue

from test_project.comments.models import FanComment


def comments_partial_view(request: HttpRequest, content_type_id: int, object_id: int):
    """Render comments for a given object as a partial template."""
    content_type = ContentType.objects.get(pk=content_type_id)

    Glue.queryset(
        request=request,
        target=FanComment.objects.filter(content_type=content_type, object_id=object_id),
        unique_name='comments',
        access=Glue.Access.DELETE,
    )

    return render(
        request,
        'comments/partial/comments_partial.html',
        {
            'content_type_id': content_type_id,
            'object_id': object_id,
        }
    )
