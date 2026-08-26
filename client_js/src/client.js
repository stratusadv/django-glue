import GlueConfig from "./config"
import GlueHttp from "./http"
import GlueView from "./view"
import {BaseGlueProxy, NAMESPACE_TO_PROXY_CLASS} from "./proxies"
import {GlueProxyError} from "./errors"
import GluePolicy from "./policy"

class GlueClient {
    constructor(context) {
        this._onMessage = null
        this._onError = null
        this._directNamespaces = new Set()
        this._proxies = new Map()

        this._config = new GlueConfig({
            ...(context.config || {}),
            urls: context.urls || {},
        })
        this.http = new GlueHttp(this._config);
        
        this.loadManifests(context.manifest_list)
    }

    onMessage(callback) {
        this._onMessage = callback
        return this
    }

    onError(callback) {
        this._onError = callback
        return this
    }

    async fetch(url, requestOptions = {}) {
        const response = await this.http.sendRequest(url, requestOptions)
        return response.data
    }

    view(url, sharedPayload = {}) {
        return new GlueView(this.http, url, sharedPayload)
    }

    loadManifests(manifest_list = []) {
        (manifest_list || []).forEach(manifest => {
            this._registerManifest(manifest)
        })
    }

    _createProxy({policy, metadata = {}, state = {}, loading_strategy = 'lazy'}) {
        const namespace = policy?.namespace || metadata?.namespace
        const ProxyClass = NAMESPACE_TO_PROXY_CLASS[namespace] || BaseGlueProxy

        if (namespace === 'function') {
            return ProxyClass.create({http: this.http, policy, metadata})
        }

        return new ProxyClass({
            http: this.http,
            policy,
            state,
            metadata,
            client: this,
            loadingStrategy: loading_strategy,
        })
    }

    _createProxyFromManifest({policy_token, metadata = {}, state = {}, loading_strategy = 'lazy'}) {
        return this._createProxy({
            policy: GluePolicy.fromSignedPolicyToken(policy_token),
            metadata,
            state,
            loading_strategy,
        })
    }

    _registerManifest({policy_token, metadata = {}, state = {}, loading_strategy = 'lazy'}) {
        const policy = GluePolicy.fromSignedPolicyToken(policy_token)
        const name = policy?.name
        const namespace = policy?.namespace || metadata?.namespace

        if (!name) {
            throw new GlueProxyError('Cannot register a Glue proxy without policy.name.')
        }

        if (!namespace) {
            throw new GlueProxyError(`No Glue proxy class registered for namespace "${namespace}".`)
        }

        const manifest = {policy, metadata, state, loading_strategy}
        const key = name === namespace ? namespace : `${namespace}.${name}`

        if (this._proxies.has(key)) {
            this._updateProxy(this._proxies.get(key), manifest)
            return
        }

        if (name === namespace) {
            if (namespace in this && !this._directNamespaces.has(namespace)) {
                throw new GlueProxyError(`Cannot register direct Glue proxy "${namespace}" because that namespace is already registered.`)
            }

            this._directNamespaces.add(namespace)
            Object.defineProperty(this, namespace, {
                get: () => this._resolveProxy(key, manifest),
                enumerable: true,
                configurable: true,
            })
            return
        }

        if (this._directNamespaces.has(namespace)) {
            throw new GlueProxyError(`Cannot register named Glue proxy "${namespace}.${name}" because that namespace is already registered directly.`)
        }

        if (!(namespace in this)) {
            this[namespace] = {}
        }

        Object.defineProperty(this[namespace], name, {
            get: () => this._resolveProxy(key, manifest),
            enumerable: true,
            configurable: true,
        })
    }

    _resolveProxy(key, manifest) {
        if (!this._proxies.has(key)) {
            this._proxies.set(key, this._createProxy(manifest))
        }

        return this._proxies.get(key)
    }

    _updateProxy(proxy, {policy, metadata, state, loading_strategy}) {
        proxy._policy = policy
        proxy._applyResponse({state, metadata, loading_strategy})

        if ('_loadAttempted' in proxy) {
            proxy._loadAttempted = false
            proxy._loadError = null
        }
    }
}

export default GlueClient
