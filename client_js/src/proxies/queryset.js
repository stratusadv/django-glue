import BaseGlueProxy from "./base"
import GlueModelProxy from "./model"

class GlueQuerySetProxy extends BaseGlueProxy {
    constructor(options) {
        super(options)
        this._modelProxies = new Map()
        this._queryParams = options.queryParams || {}
        this._queryCache = {}
        this.loading = false

        if (this._canHydrateFromState()) {
            this._syncFromResult(this._state)
        }
    }

    get items() {
        return Array.from(this)
    }

    [Symbol.iterator]() {
        if (!this._loaded && !this.loading) {
            this.loading = true
            this.all().then(() => {
                this._loaded = true
            }).finally(() => {
                this.loading = false
            })
        }

        return this._modelProxies.values()
    }

    async all() {
        if (this._loaded) {
            return this
        }

        const result = await this.query_with_params(this._queryParams)
        this._syncFromResult(result)
        this._loaded = true
        return this
    }

    async get(pk) {
        const row = await this._callAttribute('get', {pk})
        const name = row._name || row.policy?.name || `${this._name}.${pk}`
        const proxy = this._buildModelProxy(row, this._modelProxies.get(name))
        this._modelProxies.set(name, proxy)
        return proxy
    }

    async new(initial = {}) {
        const newItem = await this._callAttribute('new', {initial})
        const proxy = this._buildModelProxy(newItem)
        return proxy
    }

    _syncFromResult(result = {}) {
        const items = result.items || []
        const oldProxies = this._modelProxies
        this._modelProxies = new Map()

        items.forEach((row, index) => {
            const name = row._name || row.policy?.name || `${this._name}.${index}`
            const proxy = this._buildModelProxy(row, oldProxies.get(name))
            this._modelProxies.set(name, proxy)
        })
    }

    _buildModelProxy(row, existingProxy = null) {
        if (row instanceof GlueModelProxy) {
            row._loaded = true
            return row
        }

        const rowLoadingStrategy = row.loading_strategy || this._loadingStrategy
        let proxy = existingProxy

        if (proxy) {
            proxy._applyResponse({
                policy: row.policy,
                state: row.state,
                metadata: row.metadata || this._metadata,
                loading_strategy: rowLoadingStrategy,
            })
        } else {
            proxy = new GlueModelProxy({
                http: this._http,
                policy: row.policy,
                state: row.state,
                metadata: row.metadata || this._metadata,
                client: this._client,
                owner: this,
                loadingStrategy: rowLoadingStrategy,
            })
        }

        proxy._loaded = true
        return proxy
    }

    query(params = {}) {
        const key = JSON.stringify(params)
        if (!this._queryCache[key]) {
            this._queryCache[key] = this._cloneWithQueryParams(params)
        }
        return this._queryCache[key]
    }

    filter(filter = {}) {
        return this.query({filter})
    }

    orderBy(orderBy) {
        return this.query({order_by: orderBy})
    }

    slice(start, stop) {
        return this.query({slice: {start, stop}})
    }

    get count() {
        return this._modelProxies.size
    }

    _cloneWithQueryParams(params = {}) {
        return new this.constructor({
            http: this._http,
            policy: this._policy,
            state: {},
            metadata: this._metadata,
            client: this._client,
            owner: this._owner,
            queryParams: this._mergeQueryParams(params),
            loadingStrategy: 'lazy',
        })
    }

    _canHydrateFromState() {
        return Boolean(
            this._loaded
            && Array.isArray(this._state?.items)
            && !this._hasQueryParams()
        )
    }

    _hasQueryParams() {
        return Boolean(
            Object.keys(this._queryParams.filter || {}).length
            || Object.keys(this._queryParams.slice || {}).length
            || this._queryParams.order_by
        )
    }

    _mergeQueryParams(params = {}) {
        const mergedParams = {
            ...this._queryParams,
            ...params,
        }
        const filter = {
            ...(this._queryParams.filter || {}),
            ...(params.filter || {}),
        }
        const slice = {
            ...(this._queryParams.slice || {}),
            ...(params.slice || {}),
        }

        if (Object.keys(filter).length) {
            mergedParams.filter = filter
        } else {
            delete mergedParams.filter
        }

        if (Object.keys(slice).length) {
            mergedParams.slice = slice
        } else {
            delete mergedParams.slice
        }

        return mergedParams
    }

    _removeModelProxy(proxy) {
        this._modelProxies.delete(proxy._name)
    }

    _updateModelProxy(proxy) {
        this._modelProxies.set(proxy._name, proxy)
    }
}

export default GlueQuerySetProxy
