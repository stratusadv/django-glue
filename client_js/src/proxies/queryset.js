import { BaseGlueProxy } from "./base";
import {GlueModelProxy} from "./model";
import GlueClient from "../client";

export class GlueQuerySetProxy extends BaseGlueProxy {
    items = [];
    lastQuery = {method: 'all', params: null};
    loaded = false;
    loading = false;

    constructor(options) {
        super(options);
    }

    *[Symbol.iterator]() {
        yield* this.items
    }

    buildChildGlueModelProxy(item) {
        const proxy = new GlueModelProxy({
            proxyUniqueName: this.uniqueName,
            contextData: GlueClient.contextData[this.uniqueName],
            values: {...item}
        })

        // Forward child proxy events to the queryset's listeners
        const querysetProxy = this;
        Object.keys(proxy.actions).forEach(actionName => {
            ['before', 'after', 'error'].forEach(type => {
                proxy.addListener(actionName, (event) => {
                    querysetProxy.emitListeners(type, actionName, event);
                }, type);
            });
        });

        proxy.addListener('delete', () => querysetProxy.refresh())

        return proxy
    }

    async all() {
        if (!this.loaded || this.lastQuery?.method !== 'all') {
            this.loading = true;
            const data = await this.processAction('all');
            this.items = data.map(item => this.buildChildGlueModelProxy(item))
            this.lastQuery = {method: 'all', params: null};
            this.loaded = true;
            this.loading = false;
        }

        return this.items
    }

    async filter(filterParams) {
        if (!this.loaded || !this.isEqual(filterParams, this.lastQuery?.params)) {
            this.loading = true;
            const data = await this.processAction('filter', filterParams);
            this.items = data.map(item => this.buildChildGlueModelProxy(item));
            this.lastQuery = {method: 'filter', params: filterParams};
            this.loaded = true;
            this.loading = false;
        }

        return this.items;
    }

    isEqual(a, b) {
        if (a === b) return true;
        if (a == null || b == null) return false;
        if (Array.isArray(a) && Array.isArray(b)) {
            if (a.length !== b.length) return false;
            return a.every((val, i) => this.isEqual(val, b[i]));
        }
        if (typeof a === 'object' && typeof b === 'object') {
            const keysA = Object.keys(a);
            const keysB = Object.keys(b);
            if (keysA.length !== keysB.length) return false;
            return keysA.every(key => keysB.includes(key) && this.isEqual(a[key], b[key]));
        }
        return false;
    }

    async refresh() {
        this.items = [];
        this.loaded = false;

        const {method, params} = this.lastQuery;
        return this[method](params);
    }

    get empty() {
      return this.loaded && this.items.length === 0;
  }
}
