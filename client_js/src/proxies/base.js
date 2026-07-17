import {cloneValue} from "../utils"

class BaseGlueProxy {
    constructor({http, policy, state = {}, metadata = {}}) {
        this._http = http
        this._policy = cloneValue(policy)
        this._name = this._policy?.name
        this._state = cloneValue(state || {})
        this._metadata = cloneValue(metadata || {})
        this._listeners = {before: {}, after: {}, error: {}}
        this._onMessage = null
        this._onError = null
        this._defineCallableAttributes()
    }

    get $policy() {
        return this._policy
    }

    get $state() {
        return this._state
    }

    get $metadata() {
        return this._metadata
    }

    get $name() {
        return this._name
    }

    addListener(attribute, callback, when = 'after') {
        if (!this._listeners[when]) {
            this._listeners[when] = {}
        }
        if (!this._listeners[when][attribute]) {
            this._listeners[when][attribute] = []
        }
        this._listeners[when][attribute].push(callback)
        return this
    }

    async _call(attribute, kwargs = {}) {
        const attributeRequest = {attribute, kwargs}
        this._emit('before', attribute, {attributeRequest, object: this})

        try {
            const response = await this._http.sendAttributeRequest({
                name: this._name,
                policy: this._policy,
                state: this._state,
                attribute,
                kwargs,
            })
            this._applyResponse(response.data)
            this._processMessages(response.data)
            this._emit('after', attribute, {
                attributeRequest,
                object: this,
                proxy: this,
                response: response.data,
            })
            return response.data?.result
        } catch (error) {
            this._emit('error', attribute, {attributeRequest, object: this, proxy: this, error})
            const errorHandler = this._onError || window.Glue?._onError
            errorHandler?.({error, attribute, attributeRequest, proxy: this})
            throw error
        }
    }

    _applyResponse(data = {}) {
        if (data.policy) {
            this._policy = cloneValue(data.policy)
        }
        if (data.metadata !== undefined) {
            this._metadata = cloneValue(data.metadata || {})
        }
        if (data.policy || data.metadata !== undefined) {
            this._defineCallableAttributes()
        }
        if (data.state !== undefined) {
            this._applyState(data.state || {})
        }
    }

    _applyState(state) {
        const nextState = this._parseState(cloneValue(state || {}))
        if (!this._state || typeof this._state !== 'object') {
            this._state = nextState
            return
        }

        if (this._state.instance_data && nextState.instance_data) {
            Object.keys(this._state.instance_data).forEach(key => {
                if (!(key in nextState.instance_data)) {
                    delete this._state.instance_data[key]
                }
            })
            Object.entries(nextState.instance_data).forEach(([key, value]) => {
                this._state.instance_data[key] = value
            })
            delete nextState.instance_data
        }

        Object.keys(this._state).forEach(key => {
            if (!(key in nextState) && key !== 'instance_data') {
                delete this._state[key]
            }
        })
        Object.assign(this._state, nextState)
    }

    _parseState(state) {
        return state
    }

    _defineCallableAttributes() {
        Object.entries(this._metadata?.attributes || {}).forEach(([attributeName, spec]) => {
            if (spec?.namespace !== 'callable') {
                return
            }

            this._defineCallableAttribute(attributeName)
        })
    }

    _defineCallableAttribute(attributeName) {
        const parts = attributeName.split('.')
        const methodName = parts.pop()
        const owner = this._callableAttributeOwner(parts)

        if (owner[methodName] !== undefined) {
            return
        }

        Object.defineProperty(owner, methodName, {
            value: async function(kwargs = {}) {
                const root = this.__glue__owner || this
                return await root._call(attributeName, kwargs)
            },
            enumerable: false,
            configurable: true,
        })
    }

    _callableAttributeOwner(parts) {
        return parts.reduce((current, part) => {
            const cacheKey = `__glue__${part}`
            if (current[part] === undefined) {
                Object.defineProperty(current, part, {
                    get: function() {
                        if (!Object.prototype.hasOwnProperty.call(this, cacheKey)) {
                            Object.defineProperty(this, cacheKey, {
                                value: {},
                                enumerable: false,
                                configurable: true,
                            })
                        }
                        Object.defineProperty(this[cacheKey], '__glue__owner', {
                            value: this,
                            enumerable: false,
                            configurable: true,
                        })
                        return this[cacheKey]
                    },
                    enumerable: false,
                    configurable: true,
                })
            }
            return current[part]
        }, this)
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
        if (!data.messages?.length || typeof window === 'undefined') {
            return
        }
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
}

export default BaseGlueProxy
