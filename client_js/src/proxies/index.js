import BaseGlueProxy from "./base"
import GlueModelProxy from "./model"
import GlueQuerySetProxy from "./queryset"
import GlueFormProxy from "./form"
import GlueTemplateProxy from "./template"
import GlueFunctionProxy from "./function"

/**
 * Mapping from Python subject type names to their corresponding JavaScript proxy classes.
 * Used by {@link GlueClient} to instantiate the correct proxy type from context data.
 * @type {Object<string, Function>}
 */
export const SUBJECT_TYPE_TO_PROXY_CLASS = {
    'model': GlueModelProxy,
    'form': GlueFormProxy,
    'querySet': GlueQuerySetProxy,
    'template': GlueTemplateProxy,
    'function': GlueFunctionProxy,
}

/** @type {Function} */
window.BaseGlueProxy = BaseGlueProxy

/** @type {Function} */
window.GlueModelProxy = GlueModelProxy

/** @type {Function} */
window.GlueQuerySetProxy = GlueQuerySetProxy

/** @type {Function} */
window.GlueFormProxy = GlueFormProxy

/** @type {Function} */
window.GlueTemplateProxy = GlueTemplateProxy

/** @type {Function} */
window.GlueFunctionProxy = GlueFunctionProxy
