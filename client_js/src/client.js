import GlueConfig from "./config"
import GlueHttp from "./http"
import GlueView from "./view"
import {BaseGlueProxy, NAMESPACE_TO_PROXY_CLASS} from "./proxies"
import {GlueProxyError} from "./errors"
import GluePolicy from "./policy"
import {
    COMPONENT_NAMESPACE,
    MANIFEST_ATTRIBUTE,
    ROOT_ATTRIBUTE,
    componentRoot,
} from "./morph"

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
        this._registerComponentsWhenParsed()
    }

    // Components are read from the DOM, so the scan has to wait for the body.
    // alpine:init fires at the top of Alpine.start(), after DOMContentLoaded
    // and before Alpine walks the tree -- so every component proxy exists by
    // the time an x-data referencing one is evaluated.
    _registerComponentsWhenParsed() {
        if (typeof document === 'undefined') {
            return
        }

        document.addEventListener(
            'alpine:init',
            () => this.registerComponentsFromDom(),
            {once: true},
        )

        // Constructed after the document was already parsed (a lazily loaded
        // page, a test), in which case alpine:init may have been and gone.
        if (document.readyState !== 'loading') {
            this.registerComponentsFromDom()
        }
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

    // Registers every component whose root is in the document, reading each
    // one's manifest from its own root element.
    //
    // A component cannot travel in the page's manifest_list: that list is
    // serialized once, wherever {% django_glue_init %} sits, and in a
    // conventional layout that is the <head> -- long before any component in
    // the body has been stamped. Reading the DOM instead makes registration
    // independent of where the init tag happens to be, and lets a morphed-in
    // component bring its own fresh policy with it.
    registerComponentsFromDom(root = document) {
        const registered = []

        root.querySelectorAll(`[${MANIFEST_ATTRIBUTE}]`).forEach(element => {
            const manifest = element.getAttribute(MANIFEST_ATTRIBUTE)

            if (!manifest) {
                return
            }

            this._registerManifest(JSON.parse(manifest))
            registered.push(element.getAttribute(ROOT_ATTRIBUTE))
        })

        return registered
    }

    // Drops component registrations whose root element has left the document.
    //
    // Stamped components register flat, with no owner edges, so nothing removes
    // one when a re-render replaces it: navigating a dashboard through a month
    // of weeks would otherwise accumulate a dead proxy per day card, each
    // holding a stale policy token.
    //
    // This is a DOM-liveness heuristic, NOT state-model.md §7 disposal. It
    // cannot reach a non-rendered object, does not cascade to objects a
    // component introduced, and has no generation tracking, so it cannot stop a
    // late response from patching a new incarnation at the same name. It must
    // be deleted when real address ownership arrives, not extended --
    // a heuristic kept alongside real ownership becomes a second, conflicting
    // source of truth about liveness. See design/REINTEGRATION.md seam 3.
    sweepDisposedComponents() {
        const registered = this[COMPONENT_NAMESPACE]

        if (!registered) {
            return []
        }

        const disposed = Object.keys(registered).filter(
            name => componentRoot(name) === null,
        )

        disposed.forEach(name => {
            delete registered[name]
        })

        return disposed
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

        if (name === namespace) {
            if (namespace in this && !this._directNamespaces.has(namespace)) {
                throw new GlueProxyError(`Cannot register direct Glue proxy "${namespace}" because that namespace is already registered.`)
            }

            this._directNamespaces.add(namespace)
            Object.defineProperty(this, namespace, {
                get: () => this._createProxy(manifest),
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
            get: () => this._createProxy(manifest),
            enumerable: true,
            configurable: true,
        })
    }

}

export default GlueClient
