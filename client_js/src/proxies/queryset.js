import BaseGlueProxy from "./base"

const QUERY_CACHE_LIMIT = 64

class GlueQuerySetProxy extends BaseGlueProxy {
    constructor(options) {
        super(options)
        this._modelProxies = new Map()
        this._queryParams = {}
        this._queryCache = new Map([['{}', this]])
        this._seekKey = null
        this._hasNext = false
        this._batchSize = null
        this._total = null
        this.loading = false
    }

    get items() {
        return Array.from(this._modelProxies.values())
    }

    get batchSize() {
        return this._batchSize
    }

    get hasNext() {
        return this._hasNext
    }

    get total() {
        return this._total
    }

    [Symbol.iterator]() {
        if (!this._loaded && !this.loading) {
            this.loading = true
            this.all().finally(() => {
                this.loading = false
            })
        }
        return this._modelProxies.values()
    }

    async all({withTotal = false} = {}) {
        if (this._loaded) return this
        const params = withTotal ? {...this._queryParams, with_total: true} : this._queryParams
        this._syncFromResult(await this._callAttribute('query_with_params', params))
        this._loaded = true
        return this
    }

    async refresh() {
        for (const proxy of this._queryCache.values()) proxy._loaded = false
        return this.all()
    }

    async loadMore() {
        if (this.loading || !this.hasNext) return this._loaded ? this : this.all()
        this.loading = true
        try {
            const result = await this._callAttribute('query_with_params', {
                ...this._queryParams,
                seek_key: this._seekKey,
            })
            this._syncFromResult(result, {append: true})
        } finally {
            this.loading = false
        }
        return this
    }

    async get(pk) {
        return await this._callAttribute('get', {pk})
    }

    async new(initial = {}) {
        return await this._callAttribute('new', {initial})
    }

    async count() {
        return await this._callAttribute('count', {filter: this._queryParams.filter})
    }

    query(params = {}) {
        const queryParams = this._mergeQueryParams(params)
        const key = JSON.stringify(queryParams)
        if (!this._queryCache.has(key)) {
            const view = Object.create(Object.getPrototypeOf(this))
            Object.defineProperties(view, Object.getOwnPropertyDescriptors(this))
            view._modelProxies = new Map(this._modelProxies)
            view._queryParams = queryParams
            view._loaded = false
            this._queryCache.set(key, view)
            for (const cacheKey of this._queryCache.keys()) {
                if (this._queryCache.size <= QUERY_CACHE_LIMIT) break
                if (cacheKey !== '{}') this._queryCache.delete(cacheKey)
            }
        }
        return this._queryCache.get(key)
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

    _afterRecordRefresh() {
        const result = this._record.computedData
        if (Array.isArray(result.items) && Object.keys(this._queryParams).length === 0) {
            this._syncFromResult(result)
            this._loaded = true
        }
    }

    _syncFromResult(result = {}, {append = false} = {}) {
        const next = append ? new Map(this._modelProxies) : new Map()
        ;(result.items || []).forEach((item, index) => {
            const proxy = item?.is_glue_manifest
                ? this._client.resolveManifest(item)
                : item
            if (proxy) next.set(proxy._record?.address || String(index), proxy)
        })
        this._modelProxies = next
        this._seekKey = result.seek_key ?? null
        this._hasNext = result.has_next ?? false
        this._batchSize = result.batch_size ?? null
        if ('total' in result) this._total = result.total
    }

    _mergeQueryParams(params = {}) {
        const filter = {...(this._queryParams.filter || {}), ...(params.filter || {})}
        const slice = {...(this._queryParams.slice || {}), ...(params.slice || {})}
        const merged = {}
        if (Object.keys(filter).length) merged.filter = filter
        const orderBy = params.order_by ?? this._queryParams.order_by
        if (orderBy) merged.order_by = orderBy
        if (Object.keys(slice).length) merged.slice = slice
        return merged
    }

    _removeModelProxy(proxy) {
        this._modelProxies.delete(proxy._record.address)
    }

    _updateModelProxy(proxy) {
        this._modelProxies.set(proxy._record.address, proxy)
    }
}

export default GlueQuerySetProxy
