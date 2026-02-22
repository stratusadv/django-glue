import { BaseGlueProxy } from "./base";
import {GlueModelProxy} from "./model";
import GlueClient from "../client";

export class GlueQuerySetProxy extends BaseGlueProxy {
    postInit() {
        const baseAll = this.all.bind(this)

        this.all = async () => {
            const data = await baseAll()
            this.items = data.map(item => this.buildQuerySetItem(item))

            return this.items
        }

        const baseFilter = this.filter.bind(this)

        this.filter = async (filterParams) => {
            const data = await baseFilter(filterParams)
            this.items = data.map(item => this.buildQuerySetItem(item))

            return this.items
        }
    }

    *[Symbol.iterator]() {
        yield* this.items
    }

    buildQuerySetItem(item) {
        // TODO: Ensure that if QuerySetProxy is configured, then a ModelProxy must be configured
        return new GlueModelProxy({
            proxyUniqueName: this.uniqueName,
            contextData: GlueClient.contextData[this.uniqueName],
            actions: {
                save: {payload: {id: item.id}},
                delete: {payload: {id: item.id}},
            },
            values: {...item}
        })
    }
}
