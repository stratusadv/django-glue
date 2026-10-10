import type {GlueProxyOptions} from "../runtime/addressRegistry"
import BaseGlueProxy from "./base"
import type FieldGlue from "./fields/base"

class FieldBackedGlueProxy extends BaseGlueProxy {
    _fields: Record<string, FieldGlue>

    constructor(options: GlueProxyOptions) {
        super(options)
        this._fields = {}
    }

    get $fields(): Record<string, FieldGlue> {
        return this._fields
    }

    get $pk(): unknown {
        const pkField = this._policy?.identity?.pk_field_name || 'id'
        return this._policy?.identity?.target_pk ?? this._record.getValue(pkField)
    }

    get $key(): unknown {
        return this.$pk ?? this._name
    }

    hasErrors(fieldName: string | null = null): boolean {
        if (fieldName) {
            return Boolean(this._record.getFieldComputed(fieldName).errors?.length)
        }
        return Object.values(this._record.computedData.fields || {}).some(
            fieldData => fieldData?.errors?.length > 0
        )
    }
}

export default FieldBackedGlueProxy
