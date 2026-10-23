import type {GlueRecordProxy} from "../runtime/addressRecord"
import BaseGlueProxy from "./base"

class GlueSequenceProxy extends BaseGlueProxy {
    get items(): GlueRecordProxy[] {
        const keys = this._policy.identity?.item_keys || Object.keys(this._policy.children || {})
        return keys
            .map(key => this._registry.getProxy(this._policy.children?.[key]))
            .filter(Boolean) as GlueRecordProxy[]
    }

    get length(): number {
        return this.items.length
    }

    at(index: number): GlueRecordProxy | undefined {
        return this.items.at(index)
    }

    [Symbol.iterator](): IterableIterator<GlueRecordProxy> {
        return this.items[Symbol.iterator]()
    }
}

export default GlueSequenceProxy
