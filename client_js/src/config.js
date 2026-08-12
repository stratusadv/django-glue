class GlueConfig {
    constructor(config = {}) {
        const urls = config.urls || {}
        this.attributeUrlPath = urls.callable_attribute || '/__dg__/callable_attribute/'
        this.glueViewUrlPath = urls.glue_view || '/__dg__/glue_view/'
        this.requestTimeoutSeconds = config.requestTimeoutSeconds || 30
        this.csrfCookieName = config.csrfCookieName || 'csrftoken'
    }
}

export default GlueConfig
