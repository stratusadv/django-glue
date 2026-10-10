import type {GlueClientContext} from "./wire"

type GlueConfigOptions = Partial<GlueClientContext['config']> & {
    urls?: Partial<GlueClientContext['urls']>
}

class GlueConfig {
    attributeUrlPath: string
    glueViewMediaType: string
    requestTimeoutSeconds: number
    csrfCookieName: string

    constructor(config: GlueConfigOptions = {}) {
        const urls = config.urls || {}
        this.attributeUrlPath = urls.callable_attribute || '/__dg__/callable_attribute/'
        this.glueViewMediaType = config.glueViewMediaType || 'application/vnd.django-glue.view+json'
        this.requestTimeoutSeconds = config.requestTimeoutSeconds || 30
        this.csrfCookieName = config.csrfCookieName || 'csrftoken'
    }
}

export type {GlueConfigOptions}
export default GlueConfig
