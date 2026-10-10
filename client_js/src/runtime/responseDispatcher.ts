import type {GlueObjectEntry} from "../wire"
import type {GlueReconcileEntry, GlueRecordProxy, GlueRequestCapture} from "./addressRecord"
import type GlueAddressRegistry from "./addressRegistry"

class GlueResponseDispatcher {
    registry: GlueAddressRegistry

    constructor(registry: GlueAddressRegistry) {
        this.registry = registry
    }

    introduce(entries: GlueObjectEntry[] = []): (GlueRecordProxy | null)[] {
        return entries.map(entry => this.registry.introduce(entry))
    }

    reconcile(address: string, data: GlueReconcileEntry | null | undefined, requestCapture: GlueRequestCapture): GlueRecordProxy | null {
        const record = this.registry.getRecord(address)
        if (!record) throw new Error(`Unknown Glue address "${address}".`)
        record.reconcile(data || {}, requestCapture)
        this.registry.refresh(record)
        return record.proxy
    }
}

export default GlueResponseDispatcher
