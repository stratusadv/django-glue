import BaseGlueProxy from "./base"

class FieldBackedGlueProxy extends BaseGlueProxy {
    constructor(options) {
        super(options)
        this.loading = false
        this._loadAttempted = false
        this._loadError = null
        this._loadPromise = null
        this._fields = {}
    }

    get $fields() {
        return this._fields
    }

    get $pk() {
        const pkField = this._policy?.identity?.pk_field_name || 'id'
        return this._policy?.identity?.target_pk ?? this._record.getValue(pkField)
    }

    get $key() {
        return this.$pk ?? this._name
    }

    hasErrors(fieldName = null) {
        if (fieldName) {
            return Boolean(this._record.getFieldComputed(fieldName).errors?.length)
        }
        return Object.values(this._record.computedData.fields || {}).some(
            fieldData => fieldData?.errors?.length > 0
        )
    }

    _ensureLoaded() {
        if (this._loaded || this._loadAttempted) return this._loadPromise
        this._loadAttempted = true
        this.loading = true
        this._loadPromise = this._callAttribute('load_state')
            .then(result => {
                this._loaded = true
                return result
            })
            .catch(error => {
                this._loadError = error
            })
            .finally(() => {
                this.loading = false
            })
        return this._loadPromise
    }

    retryLoad() {
        this._loadAttempted = false
        this._loadError = null
        return this._ensureLoaded()
    }
}

export default FieldBackedGlueProxy
