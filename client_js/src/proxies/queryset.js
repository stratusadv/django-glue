import BaseGlueProxy from "./base"
import GlueModelProxy from "./model"
import GluePolicy from "../policy"

const QUERY_CACHE_LIMIT = 64

class GlueQuerySetProxy extends BaseGlueProxy {
    constructor(options) {
        super(options)
        this._modelProxies = new Map()
        this._queryParams = options.queryParams || {}
        this._queryCache = options.queryCache || new Map([[JSON.stringify(this._queryParams), this]])
        this._total = 0
        this._pageNumber = this._queryParams.page || 1
        this._pageSize = null
        this._pageCount = 1
        this.loading = false

        if (options.seed) {
            this._seedFrom(options.seed)
        }

        if (this._canHydrateFromState()) {
            this._syncFromResult(this._state)
        }
    }

    get items() {
        return Array.from(this)
    }

    get count() {
        return this._total
    }

    get pageNumber() {
        return this._pageNumber
    }

    get pageSize() {
        return this._pageSize
    }

    get pageCount() {
        return this._pageCount
    }

    get hasNext() {
        return this._pageNumber < this._pageCount
    }

    get hasPrevious() {
        return this._pageNumber > 1
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

    async loadMore() {
        if (this.loading) {
            return this
        }

        if (!this._loaded) {
            return this.all()
        }

        if (!this.hasNext) {
            return this
        }

        this.loading = true

        try {
            const result = await this.query_with_params({...this._queryParams, page: this._pageNumber + 1})
            this._syncFromResult(result, {append: true})
        } finally {
            this.loading = false
        }

        return this
    }

    async get(pk) {
        const row = await this._callAttribute('get', {pk})
        const policy = this._policyForRow(row)
        const name = row._name || policy.name || `${this._name}.${pk}`
        const proxy = this._buildModelProxy(row, this._modelProxies.get(name), policy)
        this._modelProxies.set(name, proxy)
        return proxy
    }

    async new(initial = {}) {
        const newItem = await this._callAttribute('new', {initial})
        const proxy = this._buildModelProxy(newItem)
        return proxy
    }

    _applyResponse(data = {}) {
        super._applyResponse(data)

        if (data.state !== undefined && this._canHydrateFromState()) {
            this._syncFromResult(this._state)
        }
    }

    _seedFrom(source) {
        this._modelProxies = new Map(source._modelProxies)
        this._total = source._total
        this._pageSize = source._pageSize
        this._pageCount = source._pageCount
    }

    _syncFromResult(result = {}, {append = false} = {}) {
        const items = result.items || []
        const oldProxies = this._modelProxies
        this._modelProxies = append ? new Map(oldProxies) : new Map()
        this._total = result.total ?? items.length
        this._pageNumber = result.page ?? this._pageNumber
        this._pageSize = result.page_size ?? null
        this._pageCount = result.page_count ?? 1

        items.forEach((row, index) => {
            const policy = this._policyForRow(row)
            const name = row._name || policy.name || `${this._name}.${index}`
            const proxy = this._buildModelProxy(row, oldProxies.get(name), policy)
            this._modelProxies.set(name, proxy)
        })
    }

    _policyForRow(row) {
        if (row instanceof GlueModelProxy) {
            return row._policy
        }
        return GluePolicy.fromSignedPolicyToken(row.policy_token)
    }

    _buildModelProxy(row, existingProxy = null, policy = this._policyForRow(row)) {
        if (row instanceof GlueModelProxy) {
            row._loaded = true
            return row
        }

        const rowLoadingStrategy = row.loading_strategy || this._loadingStrategy
        let proxy = existingProxy

        if (proxy) {
            proxy._applyResponse({
                policy_token: row.policy_token,
                state: row.state,
                metadata: row.metadata || this._metadata,
                loading_strategy: rowLoadingStrategy,
            })
        } else {
            proxy = new GlueModelProxy({
                http: this._http,
                policy,
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
        const queryParams = this._mergeQueryParams(params)
        const key = JSON.stringify(queryParams)

        if (!this._queryCache.has(key)) {
            this._queryCache.set(key, this._cloneWithQueryParams(queryParams))
            this._evictQueryCache()
        }

        return this._queryCache.get(key)
    }

    _evictQueryCache() {
        for (const key of this._queryCache.keys()) {
            if (this._queryCache.size <= QUERY_CACHE_LIMIT) {
                return
            }

            if (key !== '{}' && this._queryCache.get(key) !== this) {
                this._queryCache.delete(key)
            }
        }
    }

    filter(filter = {}) {
        return this.query({filter, page: 1})
    }

    orderBy(orderBy) {
        return this.query({order_by: orderBy, page: 1})
    }

    slice(start, stop) {
        return this.query({slice: {start, stop}, page: 1})
    }

    page(number) {
        return this.query({page: number})
    }

    next() {
        return this.page(this._pageNumber + 1)
    }

    previous() {
        return this.page(Math.max(1, this._pageNumber - 1))
    }

    _cloneWithQueryParams(queryParams = {}) {
        return new this.constructor({
            http: this._http,
            policy: this._policy,
            state: {},
            metadata: this._metadata,
            client: this._client,
            owner: this._owner,
            queryParams,
            queryCache: this._queryCache,
            seed: this,
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
        return Object.keys(this._queryParams).length > 0
    }

    _mergeQueryParams(params = {}) {
        const filter = {
            ...(this._queryParams.filter || {}),
            ...(params.filter || {}),
        }
        const orderBy = params.order_by ?? this._queryParams.order_by
        const slice = {
            ...(this._queryParams.slice || {}),
            ...(params.slice || {}),
        }
        const page = params.page ?? this._queryParams.page ?? 1
        const mergedParams = {}

        if (Object.keys(filter).length) {
            mergedParams.filter = filter
        }

        if (orderBy) {
            mergedParams.order_by = orderBy
        }

        if (Object.keys(slice).length) {
            mergedParams.slice = slice
        }

        if (page !== 1) {
            mergedParams.page = page
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
