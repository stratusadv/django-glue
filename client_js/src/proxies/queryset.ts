import type {GlueRecordProxy} from "../runtime/addressRecord"
import type {GlueProxyOptions} from "../runtime/addressRegistry"
import BaseGlueProxy from "./base"

const QUERY_CACHE_LIMIT = 64

// The query a view of the queryset runs: QuerySetGlue.query_with_params() in
// django_glue/glue/objects/django/queryset.py.
type GlueQueryParams = {
    filter?: Record<string, unknown>
    order_by?: unknown
    slice?: {start?: number, stop?: number}
    seek_key?: string | null
    with_total?: boolean
}

// One batch of rows, as a query returns it and as a refresh re-derives it.
// Rows arrive as addresses.
interface GlueQueryResult {
    items?: (string | GlueRecordProxy)[]
    seek_key?: string | null
    has_next?: boolean
    batch_size?: number | null
    total?: number | null
}

class GlueQuerySetProxy extends BaseGlueProxy {
    _modelProxies: Map<string, GlueRecordProxy>
    _loaded: boolean
    _queryParams: GlueQueryParams
    _queryCache: Map<string, GlueQuerySetProxy>
    _seekKey: string | null
    _hasNext: boolean
    _batchSize: number | null
    _total: number | null
    loading: boolean

    constructor(options: GlueProxyOptions) {
        super(options)
        this._modelProxies = new Map()
        this._loaded = false
        this._queryParams = {}
        this._queryCache = new Map([['{}', this]])
        this._seekKey = null
        this._hasNext = false
        this._batchSize = null
        this._total = null
        this.loading = false
    }

    get items(): GlueRecordProxy[] {
        return Array.from(this._modelProxies.values())
    }

    get batchSize(): number | null {
        return this._batchSize
    }

    get hasNext(): boolean {
        return this._hasNext
    }

    get total(): number | null {
        return this._total
    }

    [Symbol.iterator](): IterableIterator<GlueRecordProxy> {
        if (!this._loaded && !this.loading) {
            this.loading = true
            this.all().finally(() => {
                this.loading = false
            })
        }
        return this._modelProxies.values()
    }

    async all({withTotal = false}: {withTotal?: boolean} = {}): Promise<this> {
        if (this._loaded) return this
        const params = withTotal ? {...this._queryParams, with_total: true} : this._queryParams
        this._syncFromResult(await this._callAttribute('query_with_params', params) as GlueQueryResult)
        this._loaded = true
        return this
    }

    async refresh(): Promise<this> {
        for (const proxy of this._queryCache.values()) proxy._loaded = false
        return this.all()
    }

    async loadMore(): Promise<this> {
        if (this.loading || !this.hasNext) return this._loaded ? this : this.all()
        this.loading = true
        try {
            const result = await this._callAttribute('query_with_params', {
                ...this._queryParams,
                seek_key: this._seekKey,
            }) as GlueQueryResult
            this._syncFromResult(result, {append: true})
        } finally {
            this.loading = false
        }
        return this
    }

    async get(pk: unknown): Promise<unknown> {
        return await this._callAttribute('get', {pk})
    }

    async new(initial: Record<string, unknown> = {}): Promise<unknown> {
        return await this._callAttribute('new', {initial})
    }

    async count(): Promise<unknown> {
        return await this._callAttribute('count', {filter: this._queryParams.filter})
    }

    query(params: GlueQueryParams = {}): GlueQuerySetProxy {
        const queryParams = this._mergeQueryParams(params)
        const key = JSON.stringify(queryParams)
        if (!this._queryCache.has(key)) {
            const view: GlueQuerySetProxy = Object.create(Object.getPrototypeOf(this))
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
        return this._queryCache.get(key)!
    }

    filter(filter: Record<string, unknown> = {}): GlueQuerySetProxy {
        return this.query({filter})
    }

    orderBy(orderBy: unknown): GlueQuerySetProxy {
        return this.query({order_by: orderBy})
    }

    slice(start?: number, stop?: number): GlueQuerySetProxy {
        return this.query({slice: {start, stop}})
    }

    async $refresh(options: {submit?: boolean} = {}): Promise<this> {
        if (this._viewForSignedQuery() !== this) {
            this._loaded = false
            return this.all()
        }
        await super.$refresh(options)
        return this
    }

    _afterRecordRefresh(): void {
        const received = this._record.receivedComputedData
        if (!Array.isArray(received?.items)) return
        const view = this._viewForSignedQuery()
        if (!view) return
        view._syncFromResult(received as GlueQueryResult)
        view._loaded = true
    }

    _viewForSignedQuery(): GlueQuerySetProxy | undefined {
        const querySignature = ({filter, order_by: orderBy}: GlueQueryParams = {}) => JSON.stringify([
            filter && Object.keys(filter).length ? filter : null,
            orderBy ?? null,
        ])
        const signed = querySignature((this._record.policy?.state_snapshot?.last_query_params || {}) as GlueQueryParams)
        return Array.from(this._queryCache.values()).find(view => (
            !(view._queryParams.slice && Object.keys(view._queryParams.slice).length) &&
            querySignature(view._queryParams) === signed
        ))
    }

    _syncFromResult(result: GlueQueryResult = {}, {append = false}: {append?: boolean} = {}): void {
        const next = append ? new Map(this._modelProxies) : new Map<string, GlueRecordProxy>()
        ;(result.items || []).forEach((item, index) => {
            const proxy = typeof item === 'string'
                ? this._registry.getProxy(item)
                : item
            if (proxy) next.set(proxy._record?.address || String(index), proxy)
        })
        this._modelProxies = next
        this._seekKey = result.seek_key ?? null
        this._hasNext = result.has_next ?? false
        this._batchSize = result.batch_size ?? null
        if ('total' in result) this._total = result.total as number | null
    }

    _mergeQueryParams(params: GlueQueryParams = {}): GlueQueryParams {
        const filter = {...(this._queryParams.filter || {}), ...(params.filter || {})}
        const slice = {...(this._queryParams.slice || {}), ...(params.slice || {})}
        const merged: GlueQueryParams = {}
        if (Object.keys(filter).length) merged.filter = filter
        const orderBy = params.order_by ?? this._queryParams.order_by
        if (orderBy) merged.order_by = orderBy
        if (Object.keys(slice).length) merged.slice = slice
        return merged
    }

    _removeModelProxy(proxy: GlueRecordProxy): void {
        this._modelProxies.delete(proxy._record.address)
    }

    _updateModelProxy(proxy: GlueRecordProxy): void {
        this._modelProxies.set(proxy._record.address, proxy)
    }
}

export default GlueQuerySetProxy
