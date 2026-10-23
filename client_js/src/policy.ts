import type {GluePolicyPayload} from "./wire"

// A policy nested in another's attributes carries its own token; the outer
// payload does not, and takes the token it was decoded from.
type GlueDecodedPolicy = GluePolicyPayload & {token?: string}

// The constructor copies the decoded payload onto the instance.
interface GluePolicy extends GluePolicyPayload {
    token: string
}

class GluePolicy {
    static fromSignedPolicyToken(token: string): GluePolicy {
        if (typeof token !== 'string') {
            throw new TypeError('Glue policy token must be a string.')
        }

        const encodedPayload = token.split(':', 1)[0]
        if (!encodedPayload || encodedPayload.startsWith('.')) {
            throw new Error('Glue policy token must contain uncompressed Django signed JSON.')
        }

        const base64 = encodedPayload
            .replace(/-/g, '+')
            .replace(/_/g, '/')
            .padEnd(Math.ceil(encodedPayload.length / 4) * 4, '=')
        const binary = atob(base64)
        const bytes = Uint8Array.from(binary, character => character.charCodeAt(0))
        const payload: GluePolicyPayload = JSON.parse(new TextDecoder().decode(bytes))

        return this._fromDecodedPayload(payload, token)
    }

    static _fromDecodedPayload(payload: GlueDecodedPolicy, token: string = payload.token!): GluePolicy {
        const attributes = (payload.attributes || []).map(attribute => {
            if (typeof attribute !== 'object' || attribute === null) {
                return attribute
            }
            return this._fromDecodedPayload(attribute)
        })

        return new this({...payload, attributes, token})
    }

    constructor(data: GluePolicyPayload & {token: string}) {
        Object.assign(this, data)
    }
}

export default GluePolicy
