import BaseGlueProxy from "./base";
import GlueModelProxy from "./model";
import GlueClient from "../client";

/**
 * Proxy for a Django QuerySet. Provides querying, filtering, ordering, slicing,
 * and CRUD operations on collections of model instances. Each returned item is
 * a full {@link GlueModelProxy}.
 */
class GlueQuerySetProxy extends BaseGlueProxy {
    /** @type {string} */
    static name = 'querySet'

    /** @type {GlueModelProxy[]} */
    _items = [];
    /** @type {boolean} */
    _loaded = false;
    /** @type {boolean} */
    _loading = false;

    /** @type {Object} */
    _queryParams = {}
    /** @type {Object} */
    _prevQueryParams = {}

    /**
     * @param {Object} options - Constructor options.
     * @param {GlueHttp} options.http - The HTTP client instance.
     * @param {string} options.proxyUniqueName - The unique name of this proxy.
     * @param {Object} options.proxyDefinition - Serialized proxy metadata from the server.
     */
    constructor(options) {
        super(options);
    }

    /**
     * Make the queryset proxy iterable so it can be used with `for...of`.
     * @returns {Iterator<GlueModelProxy>}
     */
    * [Symbol.iterator]() {
        yield* this._items
    }

    /**
     * Build a child {@link GlueModelProxy} from a serialized item, forwarding
     * its events to the queryset's listeners.
     * @param {Object} item - Serialized model data.
     * @returns {GlueModelProxy} The child proxy.
     */
    buildChildModelProxy(item) {
        const proxy = new GlueModelProxy({
            http: this.http,
            proxyUniqueName: this._uniqueName,
            proxyDefinition: GlueClient.proxyDefinitions[this._uniqueName],
            values: {...item},
            parentQuerySet: this
        })

        // Forward child proxy events to the queryset's listeners
        const querysetProxy = this;
        Object.keys(proxy._actions).forEach(actionName => {
            ['before', 'after', 'error'].forEach(type => {
                proxy.addListener(actionName, (event) => {
                    querysetProxy.emitListeners(type, actionName, event);
                }, type);
            });
        });

        return proxy
    }

    /**
     * Query the server with optional filter/order/slice parameters. Caches results
     * and only re-queries when parameters change.
     * @param {Object|null} [queryParams] - Query parameters (filter, order_by, slice).
     * @returns {Promise<GlueModelProxy[]>} Array of model proxy instances.
     */
    async queryWithParams(queryParams = null) {
        if (queryParams) {
            this._queryParams = queryParams
        }

        if (!this._loaded || !this._isEqual(this._prevQueryParams, this._queryParams)) {
            this._loading = true;
            const data = await this._processAction('query_with_params', this._queryParams);
            this._items = data.map(item => this.buildChildModelProxy(item))
            this._prevQueryParams = this._queryParams
            this._loaded = true;
            this._loading = false;
        }

        return this._items
    }

    /**
     * Fetch all items from the queryset.
     * @returns {Promise<GlueModelProxy[]>} Array of model proxy instances.
     */
    async all() {
        return await this.queryWithParams()
    }

    /**
     * Add a filter parameter. Returns `this` for chaining.
     * @param {Object} filterParams - Filter conditions (e.g., `{done: false}`).
     * @returns {this} The queryset proxy for chaining.
     */
    filter(filterParams) {
        return this.addQueryParam('filter', filterParams)
    }

    /**
     * Add an ordering parameter. Returns `this` for chaining.
     * @param {string|string[]} orderParams - Ordering fields (e.g., `'-created_at'`).
     * @returns {this} The queryset proxy for chaining.
     */
    orderBy(orderParams) {
        return this.addQueryParam('order_by', orderParams)
    }

    /**
     * Set the start index for slicing. Returns `this` for chaining.
     * @param {number} idx - Start index.
     * @returns {this} The queryset proxy for chaining.
     */
    sliceStart(idx) {
        return this.addQueryParam('slice', {start: idx})
    }

    /**
     * Set the end index for slicing. Returns `this` for chaining.
     * @param {number} idx - Stop index.
     * @returns {this} The queryset proxy for chaining.
     */
    sliceEnd(idx) {
        return this.addQueryParam('slice', {stop: idx})
    }

    /**
     * Set both start and stop indices for slicing. Returns `this` for chaining.
     * @param {number} [start=0] - Start index.
     * @param {number|null} [stop] - Stop index.
     * @returns {this} The queryset proxy for chaining.
     */
    slice(start = 0, stop = null) {
        return this.addQueryParam('slice', {start, stop})
    }

    /**
     * Add an arbitrary query parameter. Returns `this` for chaining.
     * @param {string} type - Parameter type (e.g., 'filter', 'order_by', 'slice').
     * @param {Object} params - Parameter value.
     * @returns {this} The queryset proxy for chaining.
     */
    addQueryParam(type, params) {
        this._queryParams[type] = params
        return this
    }

    /**
     * Compare two objects for equality via JSON serialization.
     * @param {*} a - First value.
     * @param {*} b - Second value.
     * @returns {boolean} True if values are equal.
     * @private
     */
    _isEqual(a, b) {
        return JSON.stringify(a) === JSON.stringify(b);
    }

    /**
     * Clear the cache and re-query the server with the current parameters.
     * @returns {Promise<GlueModelProxy[]>} Array of model proxy instances.
     */
    async refresh() {
        this._items = [];
        this._loaded = false;

        return this.queryWithParams()
    }

    /**
     * Whether the queryset has been loaded and contains zero items.
     * @type {boolean}
     */
    get isEmpty() {
        return this._loaded && this._items.length === 0;
    }

    /**
     * Whether the queryset has been loaded from the server.
     * @type {boolean}
     */
    get isLoaded() {
        return this._loaded;
    }

    /**
     * Create a new (unsaved) model instance and prepend it to the items list.
     * @returns {Promise<GlueModelProxy[]>} Updated items array.
     */
    async prependNew() {
        return this.pushNew('start')
    }

    /**
     * Create a new (unsaved) model instance and append it to the items list.
     * @returns {Promise<GlueModelProxy[]>} Updated items array.
     */
    async appendNew() {
        return this.pushNew('end')
    }

    /**
     * Create a new model instance from server defaults and insert it at the given location.
     * @param {'start'|'end'} [location='start'] - Where to insert the new instance.
     * @returns {Promise<GlueModelProxy[]>} Updated items array.
     */
    async pushNew(location = 'start') {
        const defaults = await this._processAction('new');
        const newObj = this.buildChildModelProxy(defaults)

        if (location == 'end') {
            this._items = [...this._items, newObj]
        } else if (location == 'start') {
            this._items = [newObj, ...this._items]
        } else {
            throw new Error('Invalid location. Use "start" or "end".')
        }

        return this._items
    }

    /**
     * Bulk save data to the server, then refresh the queryset.
     * @param {Object} data - The data to save.
     * @returns {Promise<Object>} Save result.
     */
    async save(data) {
        const result = await this._processAction('save', data);
        await this.refresh();
        return result;
    }

    /**
     * Bulk delete items matching the given parameters, then refresh the queryset.
     * @param {Object} params - Delete conditions.
     * @returns {Promise<Object>} Delete result.
     */
    async delete(params) {
        const result = await this._processAction('delete', params);
        await this.refresh();
        return result;
    }
}

export default GlueQuerySetProxy;
