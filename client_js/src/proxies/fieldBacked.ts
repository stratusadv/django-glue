import type {GlueProxyOptions} from "../runtime/addressRegistry"
import BaseGlueProxy from "./base"
import type GlueValueAttribute from "./attributes/base"

class FieldBackedGlueProxy extends BaseGlueProxy {
    _valueAttributes: Record<string, GlueValueAttribute>

    constructor(options: GlueProxyOptions) {
        super(options)
        this._valueAttributes = {}
    }

    get $fields(): Record<string, GlueValueAttribute> {
        return this._valueAttributes
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
            return Boolean(this._record.getValueComputedData(fieldName).errors?.length)
        }
        return Object.values(this._record.computedData.value_attributes || {}).some(
            computedData => computedData?.errors?.length > 0
        )
    }
}

export default FieldBackedGlueProxy
