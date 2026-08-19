import {getProxyClass} from "./registry"
import GluePolicy from "../policy"
import GlueHtmlResult from "../htmlResult"

function isPlainObject(value) {
    if (value === null || typeof value !== 'object') {
        return false
    }

    const prototype = Object.getPrototypeOf(value)
    return prototype === Object.prototype || prototype === null
}

class BaseGlueProxy {
    constructor({
        http,
        policy,
        state = {},
        metadata = {},
        owner = null,
        client = null,
        loadingStrategy = 'lazy'
    }) {
        this._http = http
        if (!(policy instanceof GluePolicy)) {
            throw new TypeError('Glue proxies require a decoded GluePolicy instance.')
        }
        this._policy = policy
        this._name = policy?.name
        this._state = state || {}
        this._metadata = metadata || {}
        this._client = client
        this._listeners = {before: {}, after: {}, error: {}}
        this._onMessage = null
        this._onError = null
        this._loadingStrategy = loadingStrategy
        this._loaded = loadingStrategy === 'eager' || this._hasPopulatedState

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
        const attributeMetadata = this._metadata?.attributes?.[attribute] || {}
        this._emit('before', attribute, {attributeRequest, object: this})

        try {
            const response = await this._http.sendAttributeRequest({
                name: this._name,
                policyToken: this._policy.token,
                state: this._stateForAttribute(attributeMetadata.takes_client_state),
                attribute,
                kwargs,
            })

            this._applyResponse(response.data)

            const result = this._convertResultManifestsToProxies(response.data?.result)
            if (response.data) {
                response.data.result = result
            }

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
            const errorHandler = this._onError || window.Glue?._onError

            if (errorHandler) {
                errorHandler({error, attribute, attributeRequest, proxy: this})
            }

            // Always rethrow, even when an onError handler ran: onError is an
            // observation hook (logging, toasts), not a way to swallow the
            // failure. Callers rely on await/try-catch to know whether the
            // call actually succeeded -- silently resolving to undefined here
            // would make a failed call indistinguishable from one that
            // legitimately returned nothing.
            throw error
        }
    }

    _stateForAttribute(takesClientState) {
        if (takesClientState === false) {
            return null
        }

        if (Array.isArray(takesClientState)) {
            return Object.fromEntries(
                takesClientState
                    .filter(key => Object.prototype.hasOwnProperty.call(this._state || {}, key))
                    .map(key => [key, this._state[key]])
            )
        }

        return this._state
    }

    _applyResponse(data = {}) {
        const shouldRefreshGlueObjectAttributes = Boolean(data.policy_token || data.metadata)
        if (data.policy_token) {
            this._policy = GluePolicy.fromSignedPolicyToken(data.policy_token)
        }
        if (data.metadata !== undefined) {
            this._metadata = data.metadata || {}
        }
        if (data.state !== undefined) {
            this._applyState(data.state || {})
            this._loaded = true
        }
        if (data.loading_strategy !== undefined) {
            this._loadingStrategy = data.loading_strategy
            this._loaded = data.loading_strategy === 'eager' || this._hasPopulatedState
        }
        if (shouldRefreshGlueObjectAttributes) {
            this._refreshGlueObjectAttributes()
        }
    }

    _invalidateGlueObjectCache() {
        Object.keys(this).forEach(key => {
            if (key.startsWith('__glue_object__')) {
                delete this[key]
            }
        })
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

    get _hasPopulatedState() {
        return this._state && typeof this._state === 'object' && Object.keys(this._state).length > 0
    }

    _configureAttributeInitializers() {
        this._attributeBuilders = {
            composite: (owner, name, qualName, meta) => this._initializeCompositeAttribute(owner, name, qualName, meta),
            callable: (owner, name, qualName, meta) => this._initializeCallableAttribute(owner, name, qualName, meta),
            readonly: (owner, name, qualName, meta) => this._initializeReadOnlyAttribute(owner, name, qualName, meta),
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

    _initializeCompositeAttribute(owner, attributeName) {
        this._defineCompositeAttribute(owner, attributeName)
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

        const existingDescriptor = Object.getOwnPropertyDescriptor(owner, attributeName)
        if (existingDescriptor?.configurable) {
            delete owner[attributeName]
        } else if (existingDescriptor) {
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
        const nestedState = proxy._state?.[relativeName] || {}

        if (proxy[cacheKey]) {
            proxy[cacheKey]._policy = attributePolicy
            proxy[cacheKey]._applyResponse({
                state: nestedState,
                metadata: nestedMetadata,
            })
        }

        Object.defineProperty(owner, attributeName, {
            get() {
                if (!proxy[cacheKey]) {
                    const nestedProxy = new ProxyClass({
                        http: proxy._http,
                        policy: attributePolicy,
                        state: nestedState,
                        metadata: nestedMetadata,
                        owner: proxy,
                        client: proxy._client,
                        loadingStrategy: proxy._loadingStrategy,
                    })
                    proxy[cacheKey] = nestedProxy
                }

                return proxy[cacheKey]
            },
            enumerable: true,
            configurable: true,
        })
    }

    _initializeStateAttribute(owner, attributeName, attributeQualName, attributeMetadata) {
        Object.defineProperty(owner, attributeName, {
            get() {
                const root = this.__glue__root || this
                return root._state?.[attributeQualName]
            },
            set(value) {
                const root = this.__glue__root || this
                if (!root._state) root._state = {}
                root._state[attributeQualName] = value
            },
            enumerable: true,
            configurable: true,
        })
    }

    _initializeReadOnlyAttribute(owner, attributeName, attributeQualName) {
        Object.defineProperty(owner, attributeName, {
            get() {
                const root = this.__glue__root || this
                return root._state?.[attributeQualName]?.value
            },
            enumerable: true,
            configurable: true,
        })
    }

    _resolveAttributeOwner(parts) {
        return parts.reduce((current, part) => {
            if (current[part] === undefined) {
                this._defineCompositeAttribute(current, part)
            }

            return current[part]
        }, this)
    }

    _defineCompositeAttribute(owner, attributeName) {
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

    _refreshGlueObjectAttributes() {
        (this._policy?.attributes || []).forEach(attribute => {
            if (!attribute?.name || typeof attribute === 'string') {
                return
            }

            const parentPrefix = this._name ? `${this._name}.` : ''
            const relativeName = attribute.name.startsWith(parentPrefix)
                ? attribute.name.slice(parentPrefix.length)
                : attribute.name
            const attributeMetadata = this._metadata?.attributes?.[relativeName] || {}
            this._initializeGlueObjectAttribute(attribute, attributeMetadata)
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

    _convertResultManifestsToProxies(result) {
        if (!this._client) {
            return result
        }

        if (Array.isArray(result)) {
            return result.map(item => this._convertResultManifestsToProxies(item))
        }

        if (!result || typeof result !== 'object') {
            return result
        }

        if (this._resultIsManifest(result)) {
            return this._client._createProxyFromManifest(result)
        }

        if (this._resultIsTemplateResponse(result)) {
            this._client.loadManifests(result.manifest_list)
            return new GlueHtmlResult(result.html)
        }

        Object.keys(result).forEach(key => {
            result[key] = this._convertResultManifestsToProxies(result[key])
        })
        return result
    }

    _resultIsManifest(result) {
        return result?.is_glue_manifest === true
    }

    _resultIsTemplateResponse(result) {
        return result?.is_glue_template_response === true
    }
}

export default BaseGlueProxy
