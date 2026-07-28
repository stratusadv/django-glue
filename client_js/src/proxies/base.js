import {getProxyClass} from "./registry"

function isPlainObject(value) {
    if (value === null || typeof value !== 'object') {
        return false
    }

    const prototype = Object.getPrototypeOf(value)
    return prototype === Object.prototype || prototype === null
}

class BaseGlueProxy {
    constructor({http, policy, state = {}, metadata = {}, owner = null}) {
        this._http = http
        this._policy = policy
        this._name = policy?.name
        this._state = state || {}
        this._metadata = metadata || {}
        this._listeners = {before: {}, after: {}, error: {}}
        this._onMessage = null
        this._onError = null

        // Non-enumerable to prevent circular reference issues during serialization
        Object.defineProperty(this, '_owner', {
            value: owner,
            writable: true,
            enumerable: false,
            configurable: true,
        })

        this._initializeAttributes()
    }

    get $owner() {
        return this._owner
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

    removeListener(attribute, callback, when = 'after') {
        const listeners = this._listeners[when]?.[attribute]
        if (!listeners) {
            return this
        }

        this._listeners[when][attribute] = listeners.filter(listener => listener !== callback)
        return this
    }

    async _callAttribute(attribute, kwargs = {}) {
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

            if (errorHandler) {
                errorHandler({error, attribute, attributeRequest, proxy: this})
            }
            else {
                throw error
            }
        }
    }

    _applyResponse(data = {}) {
        if (data.policy) {
            this._policy = data.policy
        }
        if (data.metadata !== undefined) {
            this._metadata = data.metadata || {}
        }
        if (data.state !== undefined) {
            this._applyState(data.state || {})
        }
    }

    _applyState(state) {
        const nextState = state || {}
        if (!this._state || typeof this._state !== 'object') {
            this._state = nextState
            return
        }
        this._mergeState(this._state, nextState)
    }

    // We merge new state recursively here to trigger Alpine's reactivity.
    _mergeState(target, source) {
        // Remove keys not in source
        Object.keys(target).forEach(key => {
            if (!(key in source)) {
                delete target[key]
            }
        })

        // Merge source into target
        Object.keys(source).forEach(key => {
            const sourceValue = source[key]

            if (isPlainObject(sourceValue)) {
                if (!isPlainObject(target[key])) {
                    target[key] = {}
                }
                this._mergeState(target[key], sourceValue)
            } else {
                target[key] = sourceValue
            }
        })
    }

    _configureAttributeInitializers() {
        this._attributeBuilders = {
            container: (owner, name, qualName, meta) => this._initializeContainerAttribute(owner, name, qualName, meta),
            callable: (owner, name, qualName, meta) => this._initializeCallableAttribute(owner, name, qualName, meta),
            state: (owner, name, qualName, meta) => this._initializeStateAttribute(owner, name, qualName, meta),
        }
    }

    _initializeAttributes() {
        this._configureAttributeInitializers();

        (this._policy?.attributes || []).forEach(attribute => {
            if (typeof attribute === 'string') {
                const attributeMetadata = this._metadata?.attributes?.[attribute]
                if (attributeMetadata) {
                    this._initializeAttribute(attribute, attributeMetadata)
                }
            } else if (attribute?.name) {
                // Nested policy object - look up metadata by relative name
                const parentPrefix = this._name ? `${this._name}.` : ''
                const relativeName = attribute.name.startsWith(parentPrefix)
                    ? attribute.name.slice(parentPrefix.length)
                    : attribute.name
                const attributeMetadata = this._metadata?.attributes?.[relativeName] || {}
                this._initializeGlueObjectAttribute(attribute, attributeMetadata)
            }
        })

        // Set up aliases for glue object attributes (e.g., 'form' -> 'forms.default')
        this._initializeGlueObjectAliases()
    }

    _initializeGlueObjectAliases() {
        const metadataAttrs = this._metadata?.attributes || {}
        for (const [attrKey, attrMeta] of Object.entries(metadataAttrs)) {
            if (attrMeta.namespace !== 'glue') continue
            // If metadata.name differs from the attribute key, it's an alias
            const targetName = attrMeta.name
            if (!targetName || targetName === attrKey) continue

            const parts = attrKey.split('.')
            const aliasName = parts.pop()
            const owner = this._resolveAttributeOwner(parts)

            if (owner[aliasName] !== undefined) continue

            const targetParts = targetName.split('.')
            const targetAttrName = targetParts.pop()
            const targetOwner = this._resolveAttributeOwner(targetParts)

            // Create alias property that returns the same proxy
            Object.defineProperty(owner, aliasName, {
                get() {
                    return targetOwner[targetAttrName]
                },
                enumerable: true,
                configurable: true,
            })
        }
    }

    _initializeAttribute(attributeQualName, attributeMetadata) {
        const parts = attributeQualName.split('.')
        const attributeName = parts.pop()
        const owner = this._resolveAttributeOwner(parts)

        if (owner[attributeName] !== undefined) {
            return
        }

        const initializeAttribute = this._attributeBuilders[attributeMetadata.namespace]
        if (initializeAttribute) {
            initializeAttribute(owner, attributeName, attributeQualName, attributeMetadata)
        }
    }

    _initializeContainerAttribute(owner, attributeName) {
        this._defineContainerAttribute(owner, attributeName)
    }

    _initializeCallableAttribute(owner, attributeName, attributeQualName, attributeMetadata) {
        Object.defineProperty(owner, attributeName, {
            value: async function(kwargs = {}) {
                const root = owner.__glue__root || this
                return await root._callAttribute(attributeQualName, kwargs)
            },
            enumerable: false,
            configurable: true,
        })
    }

    _initializeGlueObjectAttribute(attributePolicy, attributeMetadata) {
        const attributeQualName = attributePolicy.name
        // Strip parent name prefix if present (e.g., 'gorilla.forms.default' -> 'forms.default')
        const parentPrefix = this._name ? `${this._name}.` : ''
        const relativeName = attributeQualName.startsWith(parentPrefix)
            ? attributeQualName.slice(parentPrefix.length)
            : attributeQualName

        const parts = relativeName.split('.')
        const attributeName = parts.pop()
        const owner = this._resolveAttributeOwner(parts)

        if (owner[attributeName] !== undefined) {
            return
        }

        const nestedMetadata = attributeMetadata.metadata || {}
        const nestedNamespace = attributeMetadata.glue_namespace || attributePolicy.namespace
        const ProxyClass = getProxyClass(nestedNamespace)

        if (!ProxyClass) {
            return
        }

        const proxy = this
        const cacheKey = `__glue_object__${attributePolicy.name}`

        Object.defineProperty(owner, attributeName, {
            get() {
                if (!proxy[cacheKey]) {
                    const nestedState = proxy._state?.[relativeName] || {}
                    const nestedProxy = new ProxyClass({
                        http: proxy._http,
                        policy: attributePolicy,
                        state: nestedState,
                        metadata: nestedMetadata,
                        owner: proxy,
                    })
                    // Mark as loaded if state was provided (eager loading)
                    if (Object.keys(nestedState).length > 0) {
                        nestedProxy._loaded = true
                    }
                    proxy[cacheKey] = nestedProxy
                }

                return proxy[cacheKey]
            },
            enumerable: true,
            configurable: true,
        })
    }

    _initializeStateAttribute(owner, attributeName, attributeQualName, attributeMetadata) {
        const proxy = this
        Object.defineProperty(owner, attributeName, {
            get() {
                return proxy._state?.[attributeQualName]
            },
            set(value) {
                if (!proxy._state) proxy._state = {}
                proxy._state[attributeQualName] = value
            },
            enumerable: true,
            configurable: true,
        })
    }

    _resolveAttributeOwner(parts) {
        return parts.reduce((current, part) => {
            if (current[part] === undefined) {
                this._defineContainerAttribute(current, part)
            }

            return current[part]
        }, this)
    }

    _defineContainerAttribute(owner, attributeName) {
        const cacheKey = Symbol(`__glue__${attributeName}`)

        Object.defineProperty(owner, attributeName, {
            get: function() {
                if (!Object.prototype.hasOwnProperty.call(this, cacheKey)) {
                    Object.defineProperty(this, cacheKey, {
                        value: {},
                        enumerable: false,
                        configurable: true,
                    })
                }

                Object.defineProperty(this[cacheKey], '__glue__root', {
                    value: this.__glue__root || this,
                    enumerable: false,
                    configurable: true,
                })

                return this[cacheKey]
            },
            enumerable: false,
            configurable: true,
        })
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
