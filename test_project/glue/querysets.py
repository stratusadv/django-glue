from __future__ import annotations

# Note: We're using Django's built-in session system instead of a custom model
# The SessionDataQuerySet below is commented out as it's no longer needed

# from typing_extensions import TYPE_CHECKING
# from django.db.models import QuerySet
#
# if TYPE_CHECKING:
#     from django.db.models import QuerySet
#
#
# class SessionDataQuerySet(QuerySet):
#     def recent(self) -> QuerySet:
#         return self.order_by('-created_at')
