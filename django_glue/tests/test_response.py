from django.test import TestCase

from django_glue.message import GlueMessage
from django_glue.response import GlueResponse


class GlueResponseTestCase(TestCase):
    def test_stores_result(self):
        response = GlueResponse(result=[[1, 'Chest Pound'], [2, 'Ground Slam']])

        self.assertEqual(response.result, [[1, 'Chest Pound'], [2, 'Ground Slam']])

    def test_default_result_is_none(self):
        response = GlueResponse()

        self.assertIsNone(response.result)

    def test_stores_messages_as_list(self):
        message = GlueMessage(level=GlueMessage.Level.SUCCESS, message='Saved!')

        response = GlueResponse(result={'step': 1}, messages=(message,))

        self.assertEqual(response.messages, [message])

    def test_default_messages_is_empty_list(self):
        response = GlueResponse(result={'valid': True})

        self.assertEqual(response.messages, [])

    def test_stores_status(self):
        response = GlueResponse(result={'created': True}, status=201)

        self.assertEqual(response.status, 201)

    def test_exposes_message_class(self):
        self.assertIs(GlueResponse.Message, GlueMessage)

    def test_constructor_rejects_internal_envelope_fields(self):
        with self.assertRaises(TypeError):
            GlueResponse(result={'valid': True}, state={'errors': {}})
