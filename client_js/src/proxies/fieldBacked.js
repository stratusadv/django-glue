import BaseGlueProxy from "./base"
import {parseFieldValue} from "../utils"
import {createFieldGlue} from "./fields"

class FieldBackedGlueProxy extends BaseGlueProxy {
    constructor(options) {
        super(options)
        this._ensureFieldState()
        this._defineFields()
        this._parseFieldValues()
    }

    get $fields() {
        return this._fields
    }

    get $pk() {
        const pkField = this._policy?.identity?.pk_field_name || 'id'
        return this._policy?.identity?.target_pk ?? this._state?.instance_data?.[pkField]
    }

    get $key() {
        return this.$pk ?? this.$name
    }

    hasErrors(fieldName = null) {
        if (fieldName) {
            return Boolean(this._state?.errors?.[fieldName]?.length)
        }
        return Object.keys(this._state?.errors || {}).length > 0
    }

    _ensureFieldState() {
        if (!this._state) {
            this._state = {}
        }
        if (!this._state.instance_data) {
            this._state.instance_data = {}
        }
        if (!this._state.errors) {
            this._state.errors = {}
        }
    }

    _getFieldValue(fieldName) {
        // TODO: Re-add deferred state loading
        return this._state.instance_data?.[fieldName]
    }

    _setFieldValue(fieldName, value) {
        if (!this._state.instance_data) {
            this._state.instance_data = {}
        }
        this._state.instance_data[fieldName] = value
    }

    _getFieldErrors() {
        return this._state?.errors || {}
    }

    _defineFields() {
        const nextFields = this._fields || {}
        Object.keys(nextFields).forEach(fieldName => {
            if (!this._metadata?.fields?.[fieldName]) {
                delete nextFields[fieldName]
            }
        })

        Object.entries(this._metadata?.fields || {}).forEach(([fieldName, field]) => {
            nextFields[fieldName] = createFieldGlue({
                owner: this,
                name: fieldName,
                metadata: field,
                existingField: nextFields[fieldName],
            })

            if (this[fieldName] === undefined) {
                this._defineFieldProperty(fieldName)
            }
        })

        this._fields = nextFields
        Object.values(this._fields).forEach(field => {
            if (!field?.choice_model_path && !Array.isArray(field?.choices)) {
                field.choices = []
            }
        })
    }

    _defineFieldProperty(fieldName) {
        Object.defineProperty(this, fieldName, {
            get: () => this._fields[fieldName],
            set: value => {
                this._fields[fieldName].value = value?.__glue__isFieldProxy ? value.value : value
            },
            enumerable: true,
            configurable: true,
        })
    }

    _parseFieldValues() {
        Object.keys(this._fields || {}).forEach(fieldName => {
            this._fields[fieldName].value = parseFieldValue(
                this._fields[fieldName],
                this._getFieldValue(fieldName),
            )
        })
    }

    _applyResponse(data = {}) {
        super._applyResponse(data)
        this._ensureFieldState()
        this._defineFields()
        this._parseFieldValues()
    }
}

export default FieldBackedGlueProxy
