import BaseGlueProxy from "./base"
import GlueCollectionProxy from "./collection"
import GlueFormProxy from "./form"
import GlueFormSetProxy from "./formset"
import GlueFunctionProxy from "./function"
import GlueJsonProxy from "./json"
import GlueModelProxy from "./model"
import GlueQuerySetProxy from "./queryset"
import GlueTemplateProxy from "./template"
import {getProxyClass, registerProxyClass} from "./registry"

const NAMESPACE_TO_PROXY_CLASS = {
    collection: GlueCollectionProxy,
    form: GlueFormProxy,
    formSet: GlueFormSetProxy,
    function: GlueFunctionProxy,
    json: GlueJsonProxy,
    model: GlueModelProxy,
    querySet: GlueQuerySetProxy,
    template: GlueTemplateProxy,
}

Object.entries(NAMESPACE_TO_PROXY_CLASS).forEach(([namespace, proxyClass]) => {
    registerProxyClass(namespace, proxyClass)
})

export {
    BaseGlueProxy,
    GlueCollectionProxy,
    getProxyClass,
    GlueFormProxy,
    GlueFormSetProxy,
    GlueFunctionProxy,
    GlueJsonProxy,
    GlueModelProxy,
    GlueQuerySetProxy,
    GlueTemplateProxy,
    NAMESPACE_TO_PROXY_CLASS,
    registerProxyClass,
}
