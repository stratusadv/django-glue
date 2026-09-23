import FieldBackedGlueProxy from "./fieldBacked"

class GlueModelProxy extends FieldBackedGlueProxy {
    /**
     * A draft created by `relation.new()` attaches to that relation on its
     * first save, so the save carries a refresh of the producing relation in
     * the same batch and the relation's membership reconciles in the same
     * exchange (state-model.md §4).
     */
    _singleCall(attribute, kwargs, options = {}) {
        const producer = this._record.owner
        const producerRecord = attribute === 'save' && this._policy.identity?.relation && producer?.path === null
            ? this._registry.getRecord(producer.address)
            : null
        if (!producerRecord || producerRecord.disposed || producerRecord.stale) {
            return super._singleCall(attribute, kwargs, options)
        }
        return super._singleCall(attribute, kwargs, {...options, companions: [producerRecord]})
    }
}

export default GlueModelProxy
