from __future__ import annotations

# Note: We're using Django's built-in session system instead of a custom model
# The SessionData model below is commented out as it's no longer needed

# from django.db import models
# from test_project.glue.querysets import SessionDataQuerySet

# # Simple model for session data
# class SessionData(models.Model):
#     session_id = models.CharField(max_length=255)
#     data = models.JSONField(default=dict)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
#
#     objects = SessionDataQuerySet.as_manager()
#
#     def __str__(self):
#         return f"Session {self.session_id}"
#
#     class Meta:
#         verbose_name = 'Session Data'
#         verbose_name_plural = 'Session Data'
#         db_table = 'session_data'
