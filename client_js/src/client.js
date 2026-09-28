import GlueConfig from "./config"
import GlueHttp from "./http"
import GlueView from "./view"
import {GlueProxyError} from "./errors"
import GluePolicy from "./policy"
import GlueAddressRegistry from "./runtime/addressRegistry"
import GlueAttributeMaterializer from "./runtime/attributeMaterializer"
import GlueChildBinder from "./runtime/childBinder"
import GlueResponseDispatcher from "./runtime/responseDispatcher"
import {addScopeToNode} from "./alpine"

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
        this.loadObjects(context.objects || [])
        this._registerComponentsWhenParsed()
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

    loadObjects(entries = []) {
        this._dispatcher.introduce(entries)
        entries.forEach(entry => this._registry.refresh(
            this._registry.getRecord(entry.address)
        ))
        const childAddresses = new Set(
            entries.flatMap(entry => (
                Object.values(GluePolicy.fromSignedPolicyToken(entry.policy_token).children || {})
            ))
        )
        entries
            .filter(entry => !childAddresses.has(entry.address))
            .forEach(entry => this._registerPublicEntry(entry))
    }

    _registerComponentsWhenParsed() {
        if (typeof document === 'undefined') return
        document.addEventListener('alpine:init', () => this.registerComponentsFromDom(), {once: true})
        if (document.readyState !== 'loading') this.registerComponentsFromDom()
    }

    registerComponentsFromDom(root = document) {
        const nodes = [
            ...(root.matches?.('[data-glue-address]') ? [root] : []),
            ...root.querySelectorAll('[data-glue-address]'),
        ]
        nodes.forEach(node => {
            const address = node.getAttribute('data-glue-address')
            const objects = node.getAttribute('data-glue-objects')
            if (objects && !this._registry.getRecord(address)) {
                this.loadObjects(JSON.parse(objects).filter(
                    entry => !this._registry.getRecord(entry.address),
                ))
            }
            const proxy = this._registry.getProxy(address)
            if (!proxy) return
            const parent = node.parentElement?.closest('[data-glue-address]')
            if (parent) {
                const record = this._registry.getRecord(address)
                record.owner ||= {address: parent.getAttribute('data-glue-address'), path: null}
            }
            if (!node.hasAttribute('x-data')) node.setAttribute('x-data', '{}')
            addScopeToNode(node, {component: proxy})
        })
        return nodes
    }

    from(element) {
        const root = element?.closest?.('[data-glue-address]')
        const record = root && this._registry.getRecord(root.getAttribute('data-glue-address'))
        return record && !record.disposed ? record.proxy : null
    }

    _registerPublicEntry(entry) {
        const policy = GluePolicy.fromSignedPolicyToken(entry.policy_token)
        const {name, namespace} = policy
        if (namespace === 'component') return
        if (!name) {
            throw new GlueProxyError('Cannot register a Glue proxy without policy.name.')
        }
        if (!namespace) {
            throw new GlueProxyError(`No Glue proxy class registered for namespace "${namespace}".`)
        }

        const key = name === namespace ? namespace : `${namespace}.${name}`
        this._publicAddresses.set(key, entry.address)
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
