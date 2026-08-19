class GluePolicy {
    static fromSignedPolicyToken(token) {
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
        const payload = JSON.parse(new TextDecoder().decode(bytes))

        return this._fromDecodedPayload(payload, token)
    }

    static _fromDecodedPayload(payload, token = payload.token) {
        const attributes = (payload.attributes || []).map(attribute => {
            if (typeof attribute !== 'object' || attribute === null) {
                return attribute
            }
            return this._fromDecodedPayload(attribute)
        })

        return new this({...payload, attributes, token})
    }

    constructor(data) {
        Object.assign(this, data)
    }
}

export default GluePolicy
