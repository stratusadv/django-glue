import GlueConfig from "./config"
import GlueHttp from "./http"
import GlueView from "./view"
import {GlueProxyError} from "./errors"
import GluePolicy from "./policy"
import GlueAddressRegistry from "./runtime/addressRegistry"
import GlueAttributeMaterializer from "./runtime/attributeMaterializer"
import GlueChildBinder from "./runtime/childBinder"
import GlueResponseDispatcher from "./runtime/responseDispatcher"

class GlueClient {
    constructor(context) {
        this._onMessage = null
        this._onError = null
        this._directNamespaces = new Set()
        this._publicAddresses = new Map()
        this._config = new GlueConfig({
            ...(context.config || {}),
            urls: context.urls || {},
        })
        this.http = new GlueHttp(this._config)
        const materializer = new GlueAttributeMaterializer()
        this._registry = new GlueAddressRegistry({
            client: this,
            http: this.http,
            materializer,
        })
        this._registry.childBinder = new GlueChildBinder(this._registry)
        this._dispatcher = new GlueResponseDispatcher(this._registry)
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

    loadManifests(manifestList = []) {
        this._introduceManifests(manifestList)
        const childAddresses = new Set(
            this._collectManifests(manifestList).flatMap(manifest => (
                Object.values(GluePolicy.fromSignedPolicyToken(manifest.policy_token).children || {})
            ))
        )
        ;(manifestList || [])
            .filter(manifest => !childAddresses.has(manifest.address))
            .forEach(manifest => this._registerPublicManifest(manifest))
    }

    resolveManifest(manifest) {
        this._introduceManifests([manifest])
        return this._registry.getProxy(manifest.address)
    }

    _introduceManifests(manifestList) {
        const entries = this._collectManifests(manifestList)
        this._dispatcher.introduce(entries)
        entries.forEach(entry => this._registry.refresh(
            this._registry.getRecord(entry.address)
        ))
    }

    _collectManifests(manifestList) {
        const entries = []
        const seen = new Set()
        const collect = value => {
            if (Array.isArray(value)) {
                value.forEach(collect)
                return
            }
            if (!value || typeof value !== 'object') return
            if (value.is_glue_manifest === true) {
                if (!seen.has(value.address)) {
                    seen.add(value.address)
                    entries.push(value)
                }
            }
            Object.values(value).forEach(collect)
        }
        collect(manifestList || [])
        return entries
    }

    _registerPublicManifest(manifest) {
        const policy = GluePolicy.fromSignedPolicyToken(manifest.policy_token)
        const {name, namespace} = policy
        if (!name) {
            throw new GlueProxyError('Cannot register a Glue proxy without policy.name.')
        }
        if (!namespace) {
            throw new GlueProxyError(`No Glue proxy class registered for namespace "${namespace}".`)
        }

        const key = name === namespace ? namespace : `${namespace}.${name}`
        this._publicAddresses.set(key, manifest.address)
        if (name === namespace) {
            if (namespace in this && !this._directNamespaces.has(namespace)) {
                throw new GlueProxyError(`Cannot register direct Glue proxy "${namespace}" because that namespace is already registered.`)
            }
            this._directNamespaces.add(namespace)
            Object.defineProperty(this, namespace, {
                get: () => this._registry.getProxy(this._publicAddresses.get(key)),
                enumerable: true,
                configurable: true,
            })
            return
        }

        if (this._directNamespaces.has(namespace)) {
            throw new GlueProxyError(`Cannot register named Glue proxy "${namespace}.${name}" because that namespace is already registered directly.`)
        }
        if (!(namespace in this)) this[namespace] = {}
        Object.defineProperty(this[namespace], name, {
            get: () => this._registry.getProxy(this._publicAddresses.get(key)),
            enumerable: true,
            configurable: true,
        })
    }
}

export default GlueClient
