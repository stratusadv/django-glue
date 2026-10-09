import {reactive} from "../alpine"
import type GlueClient from "../client"
import {GlueProxyError} from "../errors"
import type GlueHttp from "../http"
import GluePolicy from "../policy"
import {BaseGlueProxy, NAMESPACE_TO_PROXY_CLASS} from "../proxies"
import type {GlueObjectEntry} from "../wire"
import GlueAddressRecord from "./addressRecord"
import type {GlueRecordProxy} from "./addressRecord"
import type GlueAttributeMaterializer from "./attributeMaterializer"
import {isOwnedBy} from "./childBinder"
import type GlueChildBinder from "./childBinder"

interface GlueProxyOptions {
    http: GlueHttp
    record: GlueAddressRecord
    registry: GlueAddressRegistry
    client: GlueClient
}

interface GlueProxyClass {
    new (options: GlueProxyOptions): GlueRecordProxy
    create?(options: GlueProxyOptions): GlueRecordProxy
}

class GlueAddressRegistry {
    client: GlueClient
    http: GlueHttp
    materializer: GlueAttributeMaterializer
    childBinder: GlueChildBinder
    records: Map<string, GlueAddressRecord>

    constructor({client, http, materializer, childBinder}: {
        client: GlueClient
        http: GlueHttp
        materializer: GlueAttributeMaterializer
        childBinder?: GlueChildBinder
    }) {
        this.client = client
        this.http = http
        this.materializer = materializer
        // The binder needs the registry to exist, so the client sets it after
        // constructing both.
        this.childBinder = childBinder as GlueChildBinder
        this.records = new Map()
    }

    introduce(entry: GlueObjectEntry): GlueRecordProxy | null {
        if (!entry?.address || !entry?.policy_token) {
            throw new GlueProxyError('Glue entries require address and policy_token.')
        }
        const policy = GluePolicy.fromSignedPolicyToken(entry.policy_token)
        if (policy.address !== entry.address) {
            throw new GlueProxyError(`Glue entry address "${entry.address}" does not match its policy.`)
        }

        let record = this.records.get(entry.address)
        if (!record) {
            record = new GlueAddressRecord({
                address: entry.address,
                policyToken: entry.policy_token,
                staticData: entry.static_data,
                computedData: entry.computed_data,
            })
            this.records.set(entry.address, record)
            record.attachProxy(this._createProxy(record))
        } else {
            record.introduce(entry)
        }
        this.refresh(record)
        return record.proxy
    }

    refresh(record: GlueAddressRecord): void {
        this.materializer.refresh(record)
        this.childBinder.refresh(record)
        const displaced = record.displacedChildren
        if (displaced) {
            record.displacedChildren = null
            displaced.forEach(address => this.dispose(address))
        }
        record.proxy?._afterRecordRefresh?.()
    }

    // A record's children go with it. A child is linked to its owner only once
    // both are registered and one of them is refreshed or read, so a child that
    // arrived after its owner and was never read has no link. Its address is
    // still derived from its owner's, which is what makes it a child.
    dispose(address: string): void {
        const record = this.records.get(address)
        if (!record || record.disposed) return
        const doomed = [address]
        let index = 0
        while (index < doomed.length) {
            const current = doomed[index]
            this.records.forEach(candidate => {
                const isChild = candidate.owner?.address === current
                    || isOwnedBy(candidate.address, current)
                if (isChild && !doomed.includes(candidate.address)) {
                    doomed.push(candidate.address)
                }
            })
            index += 1
        }
        doomed.forEach(doomedAddress => {
            const doomedRecord = this.records.get(doomedAddress)
            if (!doomedRecord || doomedRecord.disposed) return
            doomedRecord.dispose()
            this.records.delete(doomedAddress)
            doomedRecord.proxy?._onDispose?.()
        })
    }

    getRecord(address: string): GlueAddressRecord | undefined {
        return this.records.get(address)
    }

    getProxy(address: string): GlueRecordProxy | null {
        return this.records.get(address)?.proxy || null
    }

    _createProxy(record: GlueAddressRecord): GlueRecordProxy {
        // The proxy classes are still JavaScript, so their types are asserted
        // here until they are converted.
        const proxyClasses = NAMESPACE_TO_PROXY_CLASS as unknown as Record<string, GlueProxyClass | undefined>
        const ProxyClass = proxyClasses[record.policy.namespace] || (BaseGlueProxy as unknown as GlueProxyClass)
        const options = {
            http: this.http,
            record,
            registry: this,
            client: this.client,
        }
        const proxy = record.policy.namespace === 'function'
            ? ProxyClass.create!(options)
            : new ProxyClass(options)
        return reactive(proxy)
    }
}

export type {GlueProxyOptions}
export default GlueAddressRegistry
