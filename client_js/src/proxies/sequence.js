import BaseGlueProxy from "./base"

class GlueSequenceProxy extends BaseGlueProxy {
    get items() {
        const keys = this._policy.identity?.item_keys || Object.keys(this._policy.children || {})
        return keys
            .map(key => this._registry.getProxy(this._policy.children?.[key]))
            .filter(Boolean)
    }

    get length() {
        return this.items.length
    }

    at(index) {
        return this.items.at(index)
    }

    [Symbol.iterator]() {
        return this.items[Symbol.iterator]()
    }
}

export default GlueSequenceProxy
