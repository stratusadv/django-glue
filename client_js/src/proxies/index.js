import {BaseGlueProxy} from "./base"
import {GlueModelProxy} from "./model"
import {GlueQuerySetProxy} from "./queryset"
import {GlueFormProxy} from "./form"

export const SUBJECT_TYPE_TO_PROXY_CLASS = {
    'Model': GlueModelProxy,
    'QuerySet': GlueQuerySetProxy,
    'BaseForm': GlueFormProxy,
}

window.BaseGlueProxy = BaseGlueProxy
window.GlueModelProxy = GlueModelProxy
window.GlueQuerySetProxy = GlueQuerySetProxy
window.GlueFormProxy = GlueFormProxy