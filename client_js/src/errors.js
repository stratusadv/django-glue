class GlueHttpError extends Error {
    constructor({message, status, code = null, payload = null, responseBody = null}) {
        super(message)
        this.name = 'GlueHttpError'
        this.status = status
        this.code = code
        this.payload = payload
        this.responseBody = responseBody
    }
}

class GlueProxyError extends Error {
    constructor(message) {
        super(message)
        this.name = 'GlueProxyError'
    }
}

export {GlueHttpError, GlueProxyError}
