import BaseGlueProxy from "./base"
import GlueModelProxy from "./model"

class GlueQuerySetProxy extends BaseGlueProxy {
    constructor(options) {
        super(options)
        this._rowProxies = new Map()
        this._queryParams = options.queryParams || {}
        this._items = []
        this._queryResults = {}
        this._resultCache = []
        this._queryLoadingKeys = new Set()
        this._queryLoadedKeys = new Set()
        this._syncItems()
        this._setQueryResult(this._queryKey({}), this._items)
    }

    get _itemPayloads() {
        return this._state?.items || []
    }

    get items() {
        return this._items
    }

    get rows() {
        return this.items
    }

    [Symbol.iterator]() {
        return this.items[Symbol.iterator]()
    }

    queryWithParams(params = {}) {
        const key = this._queryKey(params)
        if (this._queryResults[key]) {
            this._resultCache = this._queryResults[key]
            return this._resultCache
        }

        this._queryResults[key] = this._resultCache
        this._ensureQueryResult(params, key)
        return this._resultCache
    }

    query_with_params(params = {}) {
        return this.queryWithParams(params)
    }

    async fetchWithParams(params = {}) {
        const attribute = 'query_with_params'
        const attributeRequest = {attribute, kwargs: params}
        this._emit('before', attribute, {attributeRequest, object: this})

        try {
            const response = await this._http.sendAttributeRequest({
                name: this._name,
                policy: this._policy,
                state: this._state,
                attribute,
                kwargs: params,
            })
            const items = this._itemsFromResponse(response.data)
            this._processMessages(response.data)
            this._emit('after', attribute, {
                attributeRequest,
                object: this,
                proxy: this,
                response: response.data,
            })
            return items
        } catch (error) {
            this._emit('error', attribute, {attributeRequest, object: this, proxy: this, error})
            throw error
        }
    }

    async all() {
        return await this.fetchWithParams(this._queryParams)
    }

    filter(filter = {}) {
        return this._cloneWithQueryParams({filter})
    }

    orderBy(orderBy) {
        return this._cloneWithQueryParams({order_by: orderBy})
    }

    slice(start, stop) {
        return this._cloneWithQueryParams({slice: {start, stop}})
    }

    async new() {
        return await this._callAttribute('new')
    }

    _applyResponse(data = {}) {
        super._applyResponse(data)
        this._syncItems()
    }

    _syncItems() {
        const items = this._itemPayloads.map((row, index) => this._buildRowObject(row, index))
        this._items = items
        this._setQueryResult(this._queryKey({}), items)
    }

    _ensureQueryResult(params = {}, key = this._queryKey(params)) {
        if (this._queryLoadingKeys.has(key) || this._queryLoadedKeys.has(key)) {
            return
        }

        this._queryLoadingKeys.add(key)
        this.fetchWithParams(params)
            .then(items => {
                this._setQueryResult(key, items)
                this._queryLoadedKeys.add(key)
            })
            .finally(() => {
                this._queryLoadingKeys.delete(key)
            })
    }

    _setQueryResult(key, items) {
        this._queryResults[key] = items
        this._resultCache = items
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

    _queryKey(params = {}) {
        return JSON.stringify(params || {})
    }

    _itemsFromResponse(data = {}) {
        const itemPayloads = data.result?.items || data.state?.items || []
        return itemPayloads.map((row, index) => this._buildRowObject(row, index))
    }

    _buildRowObject(row, index) {
        if (row?.policy) {
            return this._getOrCreateRowProxy(row, index)
        }
        return {
            $key: row?.id ?? row?.pk ?? index,
            ...row,
        }
    }

    _getOrCreateRowProxy(row, index) {
        const name = row.policy.name || `${this._name}.${index}`
        let proxy = this._rowProxies.get(name)
        if (!proxy) {
            proxy = new GlueModelProxy({
                http: this._http,
                policy: row.policy,
                state: row.state,
                metadata: row.metadata || this._metadata,
            })
            proxy.$collection = this
            this._rowProxies.set(name, proxy)
            return proxy
        }

        proxy._applyResponse({
            policy: row.policy,
            state: row.state,
            metadata: row.metadata || this._metadata,
        })
        proxy.$collection = this
        return proxy
    }

    _removeRowProxy(proxy) {
        const rowIndex = this._itemPayloads.findIndex(row => {
            return row?.policy?.name === proxy._name
                || row?.policy?.identity?.target_pk === proxy.$pk
                || row?.id === proxy.$pk
                || row?.pk === proxy.$pk
        })

        if (rowIndex >= 0) {
            this._itemPayloads.splice(rowIndex, 1)
            this._items.splice(rowIndex, 1)
        }

        this._rowProxies.delete(proxy._name)
    }
}

export default GlueQuerySetProxy
