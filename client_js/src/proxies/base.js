import {htmlResultFromResponse} from "../htmlRenderer"

class BaseGlueProxy {
    constructor({http, record, registry, client = null, owner = null}) {
        Object.defineProperties(this, {
            _http: {value: http, enumerable: false, configurable: true},
            _record: {value: record, enumerable: false, configurable: true},
            _registry: {value: registry, enumerable: false, configurable: true},
            _client: {value: client, enumerable: false, configurable: true},
        })
        this._listeners = {before: {}, after: {}, error: {}}
        this._onMessage = null
        this._onError = null
        this._loaded = record.loadingStrategy === 'eager'

        Object.defineProperty(this, '_owner', {
            value: owner,
            writable: true,
            enumerable: false,
            configurable: true,
        })
    }

    get _policy() {
        return this._record.policy
    }

    get _name() {
        return this._record.policy.name
    }

    get $owner() {
        return this._owner
    }

    addListener(attribute, callback, when = 'after') {
        this._listeners[when] ||= {}
        this._listeners[when][attribute] ||= []
        this._listeners[when][attribute].push(callback)
        return this
    }

    removeListener(attribute, callback, when = 'after') {
        const listeners = this._listeners[when]?.[attribute]
        if (listeners) {
            this._listeners[when][attribute] = listeners.filter(listener => listener !== callback)
        }
        return this
    }

    async _callAttribute(attribute, kwargs = {}) {
        const attributeRequest = {attribute, kwargs}
        this._emit('before', attribute, {attributeRequest, object: this})

        return this._record.enqueue(async () => {
            const requestCapture = this._record.captureRequest()
            try {
                const response = await this._http.sendAttributeRequest({
                    name: this._name,
                    policyToken: this._record.policyToken,
                    updates: requestCapture.updates,
                    attribute,
                    kwargs,
                })
                this._client._introduceManifests(response.data?.manifest_list || [])
                this._client._dispatcher.reconcile(
                    this._record.address,
                    response.data,
                    requestCapture,
                )
                const result = this._convertResult(response.data?.result)
                if (response.data) response.data.result = result
                this._processMessages(response.data)
                this._emit('after', attribute, {
                    attributeRequest,
                    object: this,
                    proxy: this,
                    response: response.data,
                })
                return result
            } catch (error) {
                this._emit('error', attribute, {attributeRequest, object: this, proxy: this, error})
                const errorHandler = this._onError || globalThis.Glue?._onError
                errorHandler?.({error, attribute, attributeRequest, proxy: this})
                throw error
            }
        })
    }

    _refreshMaterializedInterface() {
        this._registry?.refresh(this._record)
    }

    onMessage(callback) {
        this._onMessage = callback
        return this
    }

    onError(callback) {
        this._onError = callback
        return this
    }

    _processMessages(data = {}) {
        if (!data.messages?.length || typeof window === 'undefined') return
        const handler = this._onMessage || window.Glue?._onMessage
        handler?.({messages: data.messages, proxy: this})
    }

    _emit(when, attribute, payload) {
        const listeners = [
            ...(this._listeners[when]?.[attribute] || []),
            ...(this._listeners[when]?.['*'] || []),
        ]
        listeners.forEach(listener => listener(payload))
    }

    _convertResult(result) {
        if (Array.isArray(result)) {
            return result.map(item => this._convertResult(item))
        }
        if (!result || typeof result !== 'object') return result
        if (result.is_glue_manifest === true) return this._client.resolveManifest(result)
        if (result.is_glue_template_response === true) {
            return htmlResultFromResponse(result, this._client)
        }
        Object.keys(result).forEach(key => {
            result[key] = this._convertResult(result[key])
        })
        return result
    }
}

export default BaseGlueProxy
