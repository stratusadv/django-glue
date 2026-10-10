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
        if (attribute === null || attribute === 'append') {
            return super._singleCall(attribute, kwargs, options)
        }
        // pop submits only the removed row, without its edits: an uncoercible
        // draft value must not block removing the row.
        const forms = attribute === 'pop'
            ? this._submittedForms([kwargs.key], false)
            : this._submittedForms()
        return super._singleCall(attribute, {...kwargs, __submitted_forms: forms}, options)
    }

    _submittedForms(keys = Object.keys(this._policy.children || {}), withUpdates = true) {
        const children = this._policy.children || {}
        return Object.fromEntries(keys.map(key => {
            const record = this._registry.getRecord(children[key])
            if (!record || record.disposed) {
                throw new Error(`Formset row "${key}" is unavailable.`)
            }
            return [key, {
                policy_token: record.policyToken,
                updates: withUpdates ? record.captureRequest().updates : {},
            }]
        }))
    }

    // A formset is submitted with its rows, as its own calls submit them.
    _submission() {
        return {...super._submission(), forms: this._submittedForms()}
    }

    async validate() {
        const result = await this._callAttribute('validate')
        this.nonFormErrors = result?.non_form_errors || []
        return result
    }
}

export default GlueFormSetProxy
