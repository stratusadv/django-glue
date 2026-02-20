import {BaseGlueProxy} from "./base"
import {GlueModelProxy} from "./model"
import {GlueQuerySetProxy} from "./queryset"

export const SUBJECT_TYPE_TO_PROXY_CLASS = {
    'Model': GlueModelProxy,
    'QuerySet': GlueQuerySetProxy
}

window.BaseGlueProxy = BaseGlueProxy
window.GlueModelProxy = GlueModelProxy
window.GlueQuerySetProxy = GlueQuerySetProxy