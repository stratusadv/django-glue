import BaseGlueProxy from "./base"

class FieldBackedGlueProxy extends BaseGlueProxy {
    constructor(options) {
        super(options)
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
}

export default FieldBackedGlueProxy
