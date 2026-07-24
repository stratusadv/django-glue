import BaseGlueProxy from "./base"
import GlueModelProxy from "./model"

class GlueQuerySetProxy extends BaseGlueProxy {
    constructor(options) {
        super(options)
        this._modelProxies = new Map()
        this._queryParams = options.queryParams || {}
        this._queryCache = {}
        this._loaded = false
        this.loading = false
    }

    get items() {
        return Array.from(this)
    }

    [Symbol.iterator]() {
        if (!this._loaded && !this.loading) {
            this.loading = true
            this.all().then(() => {
                this._loaded = true
                this.loading = false
            })
        }

        return this._modelProxies.values()
    }

    async all() {
        const result = await this.query_with_params(this._queryParams)
        this._syncFromResult(result)
        return this
    }

    _syncFromResult(result = {}) {
        const items = result.items || []
        const oldProxies = this._modelProxies
        this._modelProxies = new Map()

        items.forEach((row, index) => {
            const name = row.policy?.name || `${this._name}.${index}`
            let proxy = oldProxies.get(name)

            if (proxy) {
                proxy._applyResponse({
                    policy: row.policy,
                    state: row.state,
                    metadata: row.metadata || this._metadata,
                })
            } else {
                proxy = new GlueModelProxy({
                    http: this._http,
                    policy: row.policy,
                    state: row.state,
                    metadata: row.metadata || this._metadata,
                })
            }

            proxy._loaded = true
            proxy.$collection = this
            this._modelProxies.set(name, proxy)
        })
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
        this._modelProxies.size
    }

    async new() {
        return await this._callAttribute('new')
    }

    _cloneWithQueryParams(params = {}) {
        return new this.constructor({
            http: this._http,
            policy: this._policy,
            state: this._state,
            metadata: this._metadata,
            queryParams: this._mergeQueryParams(params),
        })
    }

    _mergeQueryParams(params = {}) {
        return {
            ...this._queryParams,
            ...params,
            filter: {
                ...(this._queryParams.filter || {}),
                ...(params.filter || {}),
            },
            slice: {
                ...(this._queryParams.slice || {}),
                ...(params.slice || {}),
            },
        }
    }

    _removeModelProxy(proxy) {
        this._modelProxies.delete(proxy._name)
    }

}

export default GlueQuerySetProxy
