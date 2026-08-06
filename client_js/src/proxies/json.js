import BaseGlueProxy from "./base"

class GlueJsonProxy extends BaseGlueProxy {
    constructor({http, policy, state = {}, metadata = {}, owner = null}) {
        super({http, policy, state, metadata, owner})
        this._value = policy?.identity?.value
    }

    get value() {
        return this._value
    }

    get length() {
        return this._value?.length
    }

    at(index) {
        return this._value?.at?.(index)
    }

    [Symbol.iterator]() {
        return this._value?.[Symbol.iterator]?.() || [][Symbol.iterator]()
    }
}

export default GlueJsonProxy
