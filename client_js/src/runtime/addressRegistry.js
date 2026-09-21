import {reactive} from "../alpine"
import {GlueProxyError} from "../errors"
import GluePolicy from "../policy"
import {BaseGlueProxy, NAMESPACE_TO_PROXY_CLASS} from "../proxies"
import GlueAddressRecord from "./addressRecord"

class GlueAddressRegistry {
    constructor({client, http, materializer, childBinder}) {
        this.client = client
        this.http = http
        this.materializer = materializer
        this.childBinder = childBinder
        this.records = new Map()
    }

    introduce(entry) {
        if (!entry?.address || !entry?.policy_token) {
            throw new GlueProxyError('Glue manifests require address and policy_token.')
        }
        const policy = GluePolicy.fromSignedPolicyToken(entry.policy_token)
        if (policy.address !== entry.address) {
            throw new GlueProxyError(`Glue manifest address "${entry.address}" does not match its policy.`)
        }

        let record = this.records.get(entry.address)
        if (!record) {
            record = new GlueAddressRecord({
                address: entry.address,
                policyToken: entry.policy_token,
                staticData: entry.static_data,
                computedData: entry.computed_data,
                loadingStrategy: entry.loading_strategy,
            })
            this.records.set(entry.address, record)
            record.attachProxy(this._createProxy(record))
        } else {
            record.introduce(entry)
        }
        this.refresh(record)
        return record.proxy
    }

    refresh(record) {
        this.materializer.refresh(record)
        this.childBinder.refresh(record)
        record.proxy?._afterRecordRefresh?.()
    }

    getRecord(address) {
        return this.records.get(address)
    }

    getProxy(address) {
        return this.records.get(address)?.proxy || null
    }

    _createProxy(record) {
        const ProxyClass = NAMESPACE_TO_PROXY_CLASS[record.policy.namespace] || BaseGlueProxy
        const options = {
            http: this.http,
            record,
            registry: this,
            client: this.client,
        }
        const proxy = record.policy.namespace === 'function'
            ? ProxyClass.create(options)
            : new ProxyClass(options)
        return reactive(proxy)
    }
}

export default GlueAddressRegistry
