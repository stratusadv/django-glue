import BaseGlueProxy from "./base"

class GlueFormSetProxy extends BaseGlueProxy {
    constructor(options) {
        super(options)
        this.nonFormErrors = []
        this._nextKey = Math.max(
            -1,
            ...Object.keys(this._policy.children || {})
                .map(Number)
                .filter(Number.isSafeInteger),
        ) + 1
    }

    get forms() {
        return Object.entries(this._policy.children || {})
            .map(([, address]) => this._registry.getProxy(address))
            .filter(Boolean)
    }

    get length() {
        return this.forms.length
    }

    async append(initial = {}) {
        const key = String(this._nextKey++)
        return await this._callAttribute('append', {key, initial})
    }

    async pop(key) {
        const entry = Object.entries(this._policy.children || {})
            .find(([, address]) => this._registry.getProxy(address)?.$key === key)
        if (!entry) return undefined
        const form = this._registry.getProxy(entry[1])
        await this._callAttribute('pop', {key: entry[0]})
        return form
    }

    _singleCall(attribute, kwargs, options = {}) {
        if (attribute !== null && attribute !== 'append' && attribute !== 'pop') {
            const forms = Object.fromEntries(
                Object.entries(this._policy.children || {}).map(([key, address]) => {
                    const record = this._registry.getRecord(address)
                    if (!record || record.disposed) {
                        throw new Error(`Formset row "${key}" is unavailable.`)
                    }
                    return [key, {
                        policy_token: record.policyToken,
                        updates: record.captureRequest().updates,
                    }]
                }),
            )
            return super._singleCall(attribute, {...kwargs, __forms: forms}, options)
        }
        return super._singleCall(attribute, kwargs, options)
    }

    async validate() {
        const result = await this._callAttribute('validate')
        this.nonFormErrors = result?.non_form_errors || []
        return result
    }
}

export default GlueFormSetProxy
