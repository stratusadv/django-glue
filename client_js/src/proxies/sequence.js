import BaseGlueProxy from "./base"
import {getProxyClass} from "./registry"
import GluePolicy from "../policy"

// A list of independent Glue objects. Items are carried in `_state.items`
// as complete manifests (policy token, state, metadata), each with its own
// identity -- not as individually named nested attributes the way a single
// object's fixed fields are (see SequenceGlue on the server for why).
class GlueSequenceProxy extends BaseGlueProxy {
    constructor(options) {
        super(options)
        this._itemProxies = new Map()
        this._syncItemsFromState()
    }

    get items() {
        return Array.from(this._itemProxies.values())
    }

    get length() {
        return this._itemProxies.size
    }

    at(index) {
        return this.items.at(index)
    }

    [Symbol.iterator]() {
        return this._itemProxies.values()
    }

    _applyResponse(data = {}) {
        super._applyResponse(data)
        if (data.state !== undefined) {
            this._syncItemsFromState()
        }
    }

    _syncItemsFromState() {
        const manifests = this._state?.items || []
        const oldProxies = this._itemProxies
        const nextProxies = new Map()

        manifests.forEach((manifest, index) => {
            const policy = GluePolicy.fromSignedPolicyToken(manifest.policy_token)
            const key = policy.name || `${this._name}.${index}`
            const existing = oldProxies.get(key)

            if (existing) {
                existing._policy = policy
                existing._applyResponse({
                    state: manifest.state,
                    metadata: manifest.metadata,
                    loading_strategy: manifest.loading_strategy,
                })
                nextProxies.set(key, existing)
                return
            }

            const ProxyClass = getProxyClass(policy.namespace) || BaseGlueProxy
            nextProxies.set(key, new ProxyClass({
                http: this._http,
                policy,
                state: manifest.state,
                metadata: manifest.metadata,
                owner: this,
                client: this._client,
                loadingStrategy: manifest.loading_strategy || this._loadingStrategy,
            }))
        })

        this._itemProxies = nextProxies
    }
}

export default GlueSequenceProxy
