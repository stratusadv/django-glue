/**
 * Global configuration for Django Glue client.
 *
 * @example
 *   const config = new GlueConfig({
 *     requestTimeoutSeconds: 30,
 *     attributeEventUrlPath: '/__dg__/bound_attribute_event/',
 *     glueViewUrlPath: '/__dg__/glue_view/',
 *   });
 */
class GlueConfig {
    /**
     * @param {Object} options - Configuration options.
     * @param {number} [options.requestTimeoutSeconds=30] - Timeout for HTTP requests in seconds.
     * @param {string} [options.attributeEventUrlPath] - URL path for bound attribute event requests.
     * @param {string} [options.glueViewUrlPath] - URL path for glue view requests.
     */
    constructor(
        {
            requestTimeoutSeconds = 30,
            attributeEventUrlPath,
            glueViewUrlPath,
        }
    ) {
        /** @type {number} */
        this.requestTimeoutSeconds = requestTimeoutSeconds
        /** @type {string} */
        this.attributeEventUrlPath = attributeEventUrlPath
        /** @type {string} */
        this.glueViewUrlPath = glueViewUrlPath
    }
}

export default GlueConfig
