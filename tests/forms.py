from django import forms


class NewYorkForm(forms.Form):
    ketchup = forms.BooleanField(required=False)
    mustard = forms.BooleanField(required=False)
    extra_toppings = forms.CharField(required=False)
    order_quantity = forms.IntegerField(min_value=1, max_value=10)


class ChicagoForm(forms.Form):
    cheese = forms.BooleanField()
    pepperoni = forms.BooleanField(required=False)
    extra_toppings = forms.CharField(required=False)
    order_quantity = forms.IntegerField(min_value=1, max_value=5)
