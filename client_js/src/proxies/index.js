import BaseGlueProxy from "./base"
import GlueSequenceProxy from "./sequence"
import GlueFormProxy from "./form"
import GlueFormSetProxy from "./formset"
import GlueFunctionProxy from "./function"
import GlueModelProxy from "./model"
import GlueQuerySetProxy from "./queryset"
import GlueTemplateProxy from "./template"
import {getProxyClass, registerProxyClass} from "./registry"

const NAMESPACE_TO_PROXY_CLASS = {
    sequence: GlueSequenceProxy,
    form: GlueFormProxy,
    formSet: GlueFormSetProxy,
    function: GlueFunctionProxy,
    model: GlueModelProxy,
    querySet: GlueQuerySetProxy,
    template: GlueTemplateProxy,
}

Object.entries(NAMESPACE_TO_PROXY_CLASS).forEach(([namespace, proxyClass]) => {
    registerProxyClass(namespace, proxyClass)
})

export {
    BaseGlueProxy,
    GlueSequenceProxy,
    getProxyClass,
    GlueFormProxy,
    GlueFormSetProxy,
    GlueFunctionProxy,
    GlueModelProxy,
    GlueQuerySetProxy,
    GlueTemplateProxy,
    NAMESPACE_TO_PROXY_CLASS,
    registerProxyClass,
}
