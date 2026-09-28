class GlueConfig {
    constructor(config = {}) {
        const urls = config.urls || {}
        this.attributeUrlPath = urls.callable_attribute || '/__dg__/callable_attribute/'
        this.glueViewMediaType = config.glueViewMediaType || 'application/vnd.django-glue.view+json'
        this.requestTimeoutSeconds = config.requestTimeoutSeconds || 30
        this.csrfCookieName = config.csrfCookieName || 'csrftoken'
    }
}

export default GlueConfig
