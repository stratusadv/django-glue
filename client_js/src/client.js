import GlueConfig from "./config"
import GlueHttp from "./http"
import GlueView from "./view"
import {NAMESPACE_TO_PROXY_CLASS} from "./proxies"
import {GlueProxyError} from "./errors"

class GlueClient {
    constructor(context) {
        // this.model = {}
        // this.querySet = {}
        // this.form = {}
        // this.template = {}
        // this.function = {}
        this.proxies = {}
        this._onMessage = null
        this._onError = null

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

    proxy(name) {
        return this.proxies[name]
    }

    async fetch(url, requestOptions = {}) {
        return await this.http.sendRequest(url, requestOptions)
    }

    view(url, sharedPayload = {}) {
        return new GlueView(this.http, url, sharedPayload)
    }

    loadManifests(manifest_list = []) {
        (manifest_list || []).forEach(glueManifest => {
            this._registerManifestAsProxy(glueManifest)
        })
    }

    _registerManifestAsProxy({policy, state = {}, metadata = {}}) {
        const name = policy?.name
        const namespace = policy?.namespace || metadata?.namespace
        const ProxyClass = NAMESPACE_TO_PROXY_CLASS[namespace]

        if (!name) {
            throw new GlueProxyError('Cannot register a Glue proxy without policy.name.')
        }

        if (!ProxyClass) {
            throw new GlueProxyError(`No Glue proxy class registered for namespace "${namespace}".`)
        }

        if (!(namespace in this)) {
            this[namespace] = {}
        }

        Object.defineProperty(this[namespace], name, {
            get: () => namespace === 'function'
            ? ProxyClass.create({http: this.http, policy, state, metadata})
            : new ProxyClass({http: this.http, policy, state, metadata})
        })
    }
}

export default GlueClient
