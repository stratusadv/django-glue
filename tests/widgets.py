import json

from django.forms import Widget

ITEM_CODE_CHOICES = (
    ('123', 'Item-123'),
    ('456', 'Item-456'),
    ('789', 'Item-789'),

)


class ItemRequestWidget(Widget):
    template_name = 'form/widget/item_request_widget.html'
    def get_context(self, name, value, attrs):
        context_data = super(ItemRequestWidget, self).get_context(name, value, attrs)
        context_data['item_code_choices'] = json.dumps(ITEM_CODE_CHOICES)
        return context_data
