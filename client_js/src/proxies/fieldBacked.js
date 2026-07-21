import BaseGlueProxy from "./base"
import {createFieldGlue} from "./fields"

class FieldBackedGlueProxy extends BaseGlueProxy {
    constructor(options) {
        super(options)
        this._loaded = false
        this.loading = false
        this._fields = {}
    }

    get $fields() {
        return this._fields
    }

    get $pk() {
        const pkField = this._policy?.identity?.pk_field_name || 'id'
        return this._policy?.identity?.target_pk ?? this._state?.[pkField]?.value
    }

    get $key() {
        return this.$pk ?? this._name
    }

    hasErrors(fieldName = null) {
        if (fieldName) {
            return Boolean(this._state?.[fieldName]?.errors?.length)
        }
        return Object.values(this._state || {}).some(
            fieldState => fieldState?.errors?.length > 0
        )
    }

    _defineStateAttribute(owner, attributeName, attributeQualName) {
        const attributeMetadata = this._metadata?.attributes?.[attributeQualName]

        this._fields[attributeName] = createFieldGlue({
            owner: this,
            name: attributeName,
            stateKey: attributeQualName,
            metadata: attributeMetadata,
            existingField: this._fields[attributeName],
        })

        Object.defineProperty(owner, attributeName, {
            get: () => {
                if (!this._loaded && !this.loading) {
                    this.loading = true
                    this._callAttribute('load').then(() => {
                        this._loaded = true
                        this.loading = false
                    })
                }
                return this._fields[attributeName]
            },
            set: (value) => {
                this._fields[attributeName].value = value?.__glue__isFieldProxy ? value.value : value
            },
            enumerable: true,
            configurable: true,
        })
    }

}

export default FieldBackedGlueProxy
