import { BaseGlueProxy } from "./base";
import {GlueModelProxy} from "./model";
import GlueClient from "../client";

export class GlueQuerySetProxy extends BaseGlueProxy {
    _items = [];
    _loaded = false;
    _loading = false;

    _queryParams = {}
    _prevQueryParams = {}

    constructor(options) {
        super(options);
    }

    *[Symbol.iterator]() {
        yield* this._items
    }

    buildChildModelProxy(item) {
        const proxy = new GlueModelProxy({
            http: this.http,
            proxyUniqueName: this._uniqueName,
            contextData: GlueClient.contextData[this._uniqueName],
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

    async all() {
        return await this.queryWithParams()
    }

    filter(filterParams) {
        return this.addQueryParam('filter', filterParams)
    }

    orderBy(orderParams) {
        return this.addQueryParam('order_by', orderParams)
    }

    sliceStart(idx) {
        return this.addQueryParam('slice', {start: idx})
    }

    sliceEnd(idx) {
        return this.addQueryParam('slice', {end: idx})
    }

    slice(start = 0, stop = null) {
        return this.addQueryParam('slice', {start, stop})
    }

    addQueryParam(type, params) {
        this._queryParams[type] = params
        return this
    }

    _isEqual(a, b) {
        return JSON.stringify(a) === JSON.stringify(b);
    }

    async refresh() {
        this._items = [];
        this._loaded = false;

        return this.queryWithParams()
    }

    get isEmpty() {
        return this._loaded && this._items.length === 0;
    }

    get isLoaded() {
        return this._loaded;
    }

    async prependNew() {
        return this.pushNew('start')
    }

    async appendNew() {
        return this.pushNew('end')
    }

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
}