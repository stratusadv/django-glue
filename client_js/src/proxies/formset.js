import BaseGlueProxy from "./base"

class GlueFormSetProxy extends BaseGlueProxy {
    constructor(options) {
        super(options)
        this.nonFormErrors = []
        this._removedKeys = new Set()
        this._nextKey = Object.keys(this._policy.children || {}).length
    }

    get forms() {
        return Object.entries(this._policy.children || {})
            .filter(([key]) => !this._removedKeys.has(key))
            .map(([, address]) => this._registry.getProxy(address))
            .filter(Boolean)
    }

    get length() {
        return this.forms.length
    }

    async append(initial = {}) {
        const key = String(this._nextKey++)
        const form = await this._callAttribute('append', {key, initial})
        this._removedKeys.delete(key)
        return form
    }

    pop(key) {
        const entry = Object.entries(this._policy.children || {})
            .find(([, address]) => this._registry.getProxy(address)?.$key === key)
        if (!entry) return undefined
        this._removedKeys.add(entry[0])
        return this._registry.getProxy(entry[1])
    }

    async validate() {
        const result = await this._callAttribute('validate')
        this._removedKeys.clear()
        this.nonFormErrors = result?.non_form_errors || []
        return result
    }
}

export default GlueFormSetProxy
