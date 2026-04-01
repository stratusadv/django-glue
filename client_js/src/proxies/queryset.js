import { BaseGlueProxy } from "./base";
import {GlueModelProxy} from "./model";
import GlueClient from "../client";

export class GlueQuerySetProxy extends BaseGlueProxy {
    $items = [];
    $loaded = false;
    $loading = false;

    $queryParams = {}
    $prevQueryParams = {}

    constructor(options) {
        super(options);
    }

    *[Symbol.iterator]() {
        yield* this.$items
    }

    buildChildModelProxy(item) {
        const proxy = new GlueModelProxy({
            proxyUniqueName: this.$uniqueName,
            contextData: GlueClient.contextData[this.$uniqueName],
            values: {...item},
            parentQuerySet: this
        })

        // Forward child proxy events to the queryset's listeners
        const querysetProxy = this;
        Object.keys(proxy.$actions).forEach(actionName => {
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
            this.$queryParams = queryParams
        }

        if (!this.$loaded || !this.$isEqual(this.$prevQueryParams, this.$queryParams)) {
            this.$loading = true;
            const data = await this.$processAction('query_with_params', this.$queryParams);
            this.$items = data.map(item => this.buildChildModelProxy(item))
            this.$prevQueryParams = this.$queryParams
            this.$loaded = true;
            this.$loading = false;
        }

        return this.$items
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
        this.$queryParams[type] = params
        return this
    }

    $isEqual(a, b) {
        return JSON.stringify(a) === JSON.stringify(b);
    }

    async refresh() {
        this.$items = [];
        this.$loaded = false;

        return this.queryWithParams()
    }

    get isEmpty() {
        return this.$loaded && this.$items.length === 0;
    }

    get isLoaded() {
        return this.$loaded;
    }

    async prependNew() {
        return this.pushNew('start')
    }

    async appendNew() {
        return this.pushNew('end')
    }

    async pushNew(location = 'start') {
        const defaults = await this.$processAction('new');
        const newObj = this.buildChildModelProxy(defaults)

        if (location == 'end') {
            this.$items = [...this.$items, newObj]
        } else if (location == 'start') {
            this.$items = [newObj, ...this.$items]
        } else {
            throw new Error('Invalid location. Use "start" or "end".')
        }

        return this.$items
    }
}