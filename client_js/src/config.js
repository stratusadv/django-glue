/**
 * Global configuration for Django Glue client.
 */

class GlueConfig {
    constructor(
        {
            requestTimeoutMs = 30000,
            sessionExpiryMessage = 'Session expired. Do you want to reload the page?',
            keepLiveIntervalSeconds = 600,
            actionUrlPath,
            keepLiveUrlPath,
            glueViewUrlPath,
        }
    ) {
        this.requestTimeoutMs = requestTimeoutMs
        this.sessionExpiryMessage = sessionExpiryMessage
        this.keepLiveIntervalSeconds = keepLiveIntervalSeconds
        this.actionUrlPath = actionUrlPath
        this.keepLiveUrlPath = keepLiveUrlPath
        this.glueViewUrlPath = glueViewUrlPath
        this.minimumKeepLiveIntervalSeconds = 120
    }
}

export default GlueConfig