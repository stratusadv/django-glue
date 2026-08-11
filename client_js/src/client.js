import GlueConfig from "./config"
import GlueHttp from "./http"
import GlueView from "./view"
import {BaseGlueProxy, NAMESPACE_TO_PROXY_CLASS} from "./proxies"
import {GlueProxyError} from "./errors"

class GlueClient {
    constructor(context) {
        this._onMessage = null
        this._onError = null
        this._directNamespaces = new Set()

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
        (manifest_list || []).forEach(glueManifest => {
            this._registerManifestAsProxy(glueManifest)
        })
    }

    hydrateGluePayloads(value) {
        if (Array.isArray(value)) {
            return value.map(item => this.hydrateGluePayloads(item))
        }

        if (!value || typeof value !== 'object') {
            return value
        }

        if (this._isGluePayload(value)) {
            return this._registerPayloadAsProxy(value)
        }

        Object.keys(value).forEach(key => {
            value[key] = this.hydrateGluePayloads(value[key])
        })
        return value
    }

    _isGluePayload(value) {
        return Boolean(
            value?.policy?.name
            && value?.policy?.namespace
            && value?.metadata !== undefined
        )
    }

    _registerPayloadAsProxy(payload) {
        const name = payload.policy.name
        const namespace = payload.policy.namespace
        this._registerManifestAsProxy(payload)

        if (name === namespace) {
            return this[namespace]
        }

        return this[namespace][name]
    }

    _registerManifestAsProxy({policy, metadata = {}, state = {}}) {
        const name = policy?.name
        const namespace = policy?.namespace || metadata?.namespace
        const ProxyClass = NAMESPACE_TO_PROXY_CLASS[namespace] || BaseGlueProxy

        if (!name) {
            throw new GlueProxyError('Cannot register a Glue proxy without policy.name.')
        }

        if (!namespace) {
            throw new GlueProxyError(`No Glue proxy class registered for namespace "${namespace}".`)
        }

        if (name === namespace) {
            if (namespace in this && !this._directNamespaces.has(namespace)) {
                throw new GlueProxyError(`Cannot register direct Glue proxy "${namespace}" because that namespace is already registered.`)
            }

            this._directNamespaces.add(namespace)
            Object.defineProperty(this, namespace, {
                get: () => namespace === 'function'
                ? ProxyClass.create({http: this.http, policy, metadata})
                : new ProxyClass({http: this.http, policy, state, metadata, client: this}),
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
            get: () => namespace === 'function'
            ? ProxyClass.create({http: this.http, policy, metadata})
            : new ProxyClass({http: this.http, policy, state, metadata, client: this}),
            configurable: true,
        })
    }
}

export default GlueClient
