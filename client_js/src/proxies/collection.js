import BaseGlueProxy from "./base"
import {getProxyClass} from "./registry"

class GlueCollectionProxy extends BaseGlueProxy {
    constructor(options) {
        super(options)
        if (!this._itemProxyCache) {
            this._itemProxyCache = new Map()
        }
    }

    get items() {
        return this._itemProxies()
    }

    get length() {
        return this.items.length
    }

    at(index) {
        return this.items.at(index)
    }

    [Symbol.iterator]() {
        return this.items[Symbol.iterator]()
    }

    _itemProxies() {
        if (!this._itemProxyCache) {
            this._itemProxyCache = new Map()
        }

        const itemPolicies = (this._policy?.attributes || [])
            .filter(attribute => typeof attribute !== 'string')
        const currentKeys = new Set(
            itemPolicies.map((policy, index) => policy.name || `${this._name}.${index}`)
        )

        Array.from(this._itemProxyCache.keys()).forEach(key => {
            if (!currentKeys.has(key)) {
                this._itemProxyCache.delete(key)
            }
        })

        return itemPolicies.map((policy, index) => this._buildItemProxy(policy, index))
    }

    _buildItemProxy(policy, index) {
        const metadata = this._metadata?.attributes?.[`items.${index}`]?.metadata || {}
        const state = this._state?.[`items.${index}`] || {}
        const ProxyClass = getProxyClass(policy.namespace) || BaseGlueProxy
        const cacheKey = policy.name || `${this._name}.${index}`
        const cachedItem = this._itemProxyCache.get(cacheKey)

        if (cachedItem) {
            if (
                cachedItem.policy !== policy
                || cachedItem.state !== state
                || cachedItem.metadata !== metadata
            ) {
                cachedItem.proxy._applyResponse({policy, state, metadata})
                this._markLoadedFromState(cachedItem.proxy, state)
                cachedItem.policy = policy
                cachedItem.state = state
                cachedItem.metadata = metadata
            }

            return cachedItem.proxy
        }

        const proxy = new ProxyClass({
            http: this._http,
            policy,
            state,
            metadata,
            owner: this,
            client: this._client,
        })
        this._markLoadedFromState(proxy, state)
        this._itemProxyCache.set(cacheKey, {
            proxy,
            policy,
            state,
            metadata,
        })

        return proxy
    }

    _markLoadedFromState(proxy, state) {
        if (Object.keys(state || {}).length > 0) {
            proxy._loaded = true
        }
    }
}

export default GlueCollectionProxy
