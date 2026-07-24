import GlueFormProxy from "./form"
import GlueFunctionProxy from "./function"
import GlueModelProxy from "./model"
import GlueQuerySetProxy from "./queryset"
import GlueTemplateProxy from "./template"

const NAMESPACE_TO_PROXY_CLASS = {
    form: GlueFormProxy,
    function: GlueFunctionProxy,
    model: GlueModelProxy,
    querySet: GlueQuerySetProxy,
    template: GlueTemplateProxy,
}

export {
    GlueFormProxy,
    GlueFunctionProxy,
    GlueModelProxy,
    GlueQuerySetProxy,
    GlueTemplateProxy,
    NAMESPACE_TO_PROXY_CLASS
}
