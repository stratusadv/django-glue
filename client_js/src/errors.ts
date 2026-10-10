import type {GlueErrorData} from "./wire"

// The owner an address error points at: the object that can reintroduce the
// address, or whose call produced it.
interface GlueOwnerReference {
    name: string
    address: string
}

class GlueHttpError extends Error {
    status: number
    code: string | null
    payload: GlueErrorData | null
    responseBody: string | null

    constructor({message, status, code = null, payload = null, responseBody = null}: {
        message: string
        status: number
        code?: string | null
        payload?: GlueErrorData | null
        responseBody?: string | null
    }) {
        super(message)
        this.name = 'GlueHttpError'
        this.status = status
        this.code = code
        this.payload = payload
        this.responseBody = responseBody
    }
}

class GlueProxyError extends Error {
    constructor(message: string) {
        super(message)
        this.name = 'GlueProxyError'
    }
}

class GlueAddressError extends GlueProxyError {
    code: string
    address: string
    owner: GlueOwnerReference | null
    status: number | null
    details: Record<string, unknown>

    constructor(
        code: string,
        message: string,
        address: string,
        owner: GlueOwnerReference | null = null,
        {status = null, details = {}}: {status?: number | null, details?: Record<string, unknown>} = {},
    ) {
        super(`Glue request for address "${address}" failed: ${message}`)
        this.name = 'GlueAddressError'
        this.code = code
        this.address = address
        this.owner = owner
        this.status = status
        this.details = details
    }
}

class GlueAlpineError extends Error {
    constructor(message: string) {
        super(message)
        this.name = 'GlueAlpineError'
    }
}

export type {GlueOwnerReference}
export {GlueAddressError, GlueAlpineError, GlueHttpError, GlueProxyError}
