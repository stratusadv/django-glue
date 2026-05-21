/**
 * Global configuration for Django Glue client.
 *
 * @example
 *   const config = new GlueConfig({
 *     requestTimeoutSeconds: 30,
 *     sessionExpiryMessage: 'Session expired.',
 *     keepLiveIntervalSeconds: 600,
 *     actionUrlPath: '/__dg__/action/',
 *     keepLiveUrlPath: '/__dg__/keep_live/',
 *     glueViewUrlPath: '/__dg__/glue_view/',
 *   });
 */
class GlueConfig {
    /**
     * @param {Object} options - Configuration options.
     * @param {number} [options.requestTimeoutSeconds=30] - Timeout for HTTP requests in seconds.
     * @param {string} [options.sessionExpiryMessage] - Message shown when session expires.
     * @param {number} [options.keepLiveIntervalSeconds=600] - Keep-alive polling interval in seconds.
     * @param {string} [options.actionUrlPath] - URL path for action requests.
     * @param {string} [options.keepLiveUrlPath] - URL path for keep-alive requests.
     * @param {string} [options.glueViewUrlPath] - URL path for glue view requests.
     */
    constructor(
        {
            requestTimeoutSeconds = 30,
            sessionExpiryMessage = 'Session expired. Do you want to reload the page?',
            keepLiveIntervalSeconds = 600,
            actionUrlPath,
            keepLiveUrlPath,
            glueViewUrlPath,
        }
    ) {
        /** @type {number} */
        this.requestTimeoutSeconds = requestTimeoutSeconds
        /** @type {string} */
        this.sessionExpiryMessage = sessionExpiryMessage
        /** @type {number} */
        this.keepLiveIntervalSeconds = keepLiveIntervalSeconds
        /** @type {string} */
        this.actionUrlPath = actionUrlPath
        /** @type {string} */
        this.keepLiveUrlPath = keepLiveUrlPath
        /** @type {string} */
        this.glueViewUrlPath = glueViewUrlPath
        /** @type {number} */
        this.minimumKeepLiveIntervalSeconds = 120
    }
}

export default GlueConfig
