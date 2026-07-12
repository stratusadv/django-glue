import json

from django.test import TestCase

from django_glue.message import GlueMessage
from django_glue.response import GlueResponse


class GlueResponseTestCase(TestCase):
    def test_preserves_list_payload_result(self):
        response = GlueResponse(
            result=[[1, 'Chest Pound'], [2, 'Ground Slam']],
            state={'errors': {}},
        ).to_json_response()

        data = json.loads(response.content)

        self.assertEqual(data['result'], [[1, 'Chest Pound'], [2, 'Ground Slam']])
        self.assertEqual(data['state'], {'errors': {}})

    def test_preserves_dict_payload_result(self):
        response = GlueResponse(
            result={'valid': True},
            state={'errors': {}},
        ).to_json_response()

        data = json.loads(response.content)

        self.assertEqual(data['result'], {'valid': True})

    def test_includes_messages_in_dict_result(self):
        message = GlueMessage(level=GlueMessage.Level.SUCCESS, message='Saved!')
        response = GlueResponse(
            result={'step': 1},
            state={'errors': {}},
            messages=[message],
        ).to_json_response()

        data = json.loads(response.content)

        self.assertEqual(data['result']['step'], 1)
        self.assertEqual(len(data['messages']), 1)
        self.assertEqual(data['messages'][0]['message'], 'Saved!')

    def test_includes_messages_in_non_dict_result(self):
        message = GlueMessage(level=GlueMessage.Level.INFO, message='Done')
        response = GlueResponse(
            result=[1, 2, 3],
            state=None,
            messages=[message],
        ).to_json_response()

        data = json.loads(response.content)

        self.assertEqual(data['result'], [1, 2, 3])
        self.assertEqual(data['messages'][0]['message'], 'Done')

    def test_exposes_message_class(self):
        self.assertIs(GlueResponse.Message, GlueMessage)

    def test_no_messages_excludes_messages_key(self):
        response = GlueResponse(
            result={'valid': True},
            state=None,
        ).to_json_response()

        data = json.loads(response.content)

        self.assertEqual(data['result'], {'valid': True})
        self.assertNotIn('messages', data)
