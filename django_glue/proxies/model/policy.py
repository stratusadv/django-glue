from django_glue.proxies.form.policy import BaseGlueFormPolicyDetails



class GlueModelPolicyDetails(BaseGlueFormPolicyDetails):
    model_class_path: str
