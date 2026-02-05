import django_glue as dg

def fake_view(request):
    new_model = Model.objects.create()

    dg.glue_model_object(
        model_object=new_model,
        access='read',
    )
