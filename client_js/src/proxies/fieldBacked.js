import BaseGlueProxy from "./base"
import {parseFieldValue} from "../utils"
import {createFieldGlue} from "./fields"

class FieldBackedGlueProxy extends BaseGlueProxy {
    constructor(options) {
        super(options)
        this.loading = false

        this._state === {} && this._initializeState()

        this._initializeFields()

        // this._ensureFieldState()
        // this._defineFields()
        // this._parseFieldValues()
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
        if (Object.keys(this._state.instance_data).length == 0 && !this.loading) {
            this.loading = true
            this._call('load').then(() => {
                console.log(fieldName, 'lodaded')
                this.loading = false
            })
        }
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
            get: function () { this._fields[fieldName] },
            set: function (value) {
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
        super._applyResponse.bind(this).call(data)
        this._ensureFieldState()
        this._defineFields()
        this._parseFieldValues()
    }

    _initializeState() {
        if (this._state === {}) {
            this._state.instance_data
        }
    }

    _initializeFields() {
        Object.entries(this._metadata.fields).forEach(([fieldName, fieldDefinition]) => {
            this._state.instance_data
        })
        console.log(this._metadata)
    }
}

export default FieldBackedGlueProxy
