import BaseGlueProxy from "./base"
import {getProxyClass} from "./registry"

class GlueFormSetProxy extends BaseGlueProxy {
    constructor(options) {
        super(options)
        this._formProxyCache = new Map()
        this._formProxies = this._initialForms()
        this._nextKey = this._formProxies.size
        this.nonFormErrors = []
        // True once append()/pop() has diverged from the server's last-known
        // form list. While true, an incidental _applyResponse (e.g. triggered
        // by an unrelated attribute call on a parent object refreshing this
        // cached nested formset) must not rebuild _formProxies from server
        // policy/state, or it would silently discard the pending local edit.
        // Cleared once the forms are genuinely refreshed from an
        // authoritative source (validate()).
        this._hasPendingLocalEdit = false
    }

    get forms() {
        return Array.from(this._formProxies.values())
    }

    get length() {
        return this._formProxies.size
    }

    async append(initial = {}) {
        const key = String(this._nextKey++)
        const form = await this._callAttribute('append', {key, initial})
        this._formProxies = new Map(this._formProxies).set(key, form)
        this._hasPendingLocalEdit = true
        return form
    }

    // Removes by the form's own stable identity ($key: $pk ?? _name), not
    // array position. x-for loops over `forms` re-render as the underlying
    // Map changes shape (append/pop); keying removal off position would let
    // a stale DOM node/Alpine scope -- still bound to a form object that no
    // longer occupies that position -- silently edit or remove the wrong
    // entry. Since $key is exactly what an `:key="form.$key"` binding should
    // use too, DOM identity and removal identity stay in agreement.
    pop(key) {
        const entry = Array.from(this._formProxies.entries())
            .find(([, form]) => form.$key === key)
        if (!entry) return undefined

        const [mapKey, removed] = entry
        const nextEntries = Array.from(this._formProxies.entries())
            .filter(([existingKey]) => existingKey !== mapKey)
        this._formProxies = new Map(nextEntries)
        this._hasPendingLocalEdit = true
        return removed
    }

    async validate() {
        const result = await this._callAttribute('validate')
        this._formProxies = new Map(
            (result?.form_list || []).map((form, index) => [String(index), form])
        )
        this._hasPendingLocalEdit = false
        this.nonFormErrors = result?.non_form_errors || []
        return result
    }

    _stateForAttribute(takesClientState) {
        if (takesClientState === false) {
            return null
        }
        return {form_list: this.forms.map(form => form._state)}
    }

    _applyResponse(data = {}) {
        super._applyResponse(data)
        if (this._hasPendingLocalEdit || !(data.policy_token || data.metadata || data.state)) return

        this._formProxies = this._initialForms()
    }

    // Mirrors GlueSequenceProxy's inline item-derivation (sequence.js)
    // -- same policy/state/metadata-keyed cache-and-rebuild shape, keyed
    // under 'form_list.{index}' and filtered to nested `form` policies instead
    // of the unfiltered item list a sequence uses.
    _initialForms() {
        if (!this._formProxyCache) {
            this._formProxyCache = new Map()
        }

        const formPolicies = (this._policy?.attributes || [])
            .filter(attribute => typeof attribute !== 'string' && attribute.namespace === 'form')
        const currentKeys = new Set(
            formPolicies.map((policy, index) => policy.name || `${this._name}.${index}`)
        )

        Array.from(this._formProxyCache.keys()).forEach(key => {
            if (!currentKeys.has(key)) {
                this._formProxyCache.delete(key)
            }
        })

        return new Map(
            formPolicies.map((policy, index) => [String(index), this._buildFormProxy(policy, index)])
        )
    }

    _buildFormProxy(policy, index) {
        const attributeKey = `form_list.${index}`
        const metadata = this._metadata?.attributes?.[attributeKey]?.metadata || {}
        const state = this._state?.[attributeKey] || {}
        const ProxyClass = getProxyClass(policy.namespace) || BaseGlueProxy
        const cacheKey = policy.name || `${this._name}.${index}`
        const cachedForm = this._formProxyCache.get(cacheKey)

        if (cachedForm) {
            if (
                cachedForm.policy !== policy
                || cachedForm.state !== state
                || cachedForm.metadata !== metadata
            ) {
                cachedForm.proxy._policy = policy
                cachedForm.proxy._applyResponse({state, metadata, loading_strategy: this._loadingStrategy})
                cachedForm.policy = policy
                cachedForm.state = state
                cachedForm.metadata = metadata
            }

            return cachedForm.proxy
        }

        const proxy = new ProxyClass({
            http: this._http,
            policy,
            state,
            metadata,
            owner: this,
            client: this._client,
            loadingStrategy: this._loadingStrategy,
        })
        this._formProxyCache.set(cacheKey, {
            proxy,
            policy,
            state,
            metadata,
        })

        return proxy
    }
}

export default GlueFormSetProxy
