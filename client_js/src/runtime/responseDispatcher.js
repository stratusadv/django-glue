class GlueResponseDispatcher {
    constructor(registry) {
        this.registry = registry
    }

    introduce(entries = []) {
        return entries.map(entry => this.registry.introduce(entry))
    }

    reconcile(address, data, requestCapture) {
        const record = this.registry.getRecord(address)
        if (!record) throw new Error(`Unknown Glue address "${address}".`)
        record.reconcile(data || {}, requestCapture)
        this.registry.refresh(record)
        return record.proxy
    }
}

export default GlueResponseDispatcher
