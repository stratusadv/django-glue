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

class GlueAddressError extends GlueProxyError {
    constructor(code, message, address, owner = null) {
        super(`Glue request for address "${address}" failed: ${message}`)
        this.name = 'GlueAddressError'
        this.code = code
        this.address = address
        this.owner = owner
    }
}

class GlueAlpineError extends Error {
    constructor(message) {
        super(message)
        this.name = 'GlueAlpineError'
    }
}

export {GlueAddressError, GlueAlpineError, GlueHttpError, GlueProxyError}
