import BaseGlueProxy from "./base"
import {createFieldGlue} from "./fields"

class FieldBackedGlueProxy extends BaseGlueProxy {
    constructor(options) {
        super(options)
        this.loading = false
        this._loadAttempted = false
        this._loadError = null
        this._loadPromise = null
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

    _ensureLoaded() {
        if (this._loaded || this._loadAttempted) {
            return this._loadPromise
        }

        this._loadAttempted = true
        this.loading = true
        this._loadPromise = this._callAttribute('load_state')
            .catch(error => {
                // Property getters cannot await or handle this failure. Retain it
                // for inspection and suppress automatic retries on every render.
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

    _configureAttributeInitializers() {
        super._configureAttributeInitializers()
        this._fields = {}
        this._attributeBuilders.field = (owner, name, qualName, meta) => this._initializeFieldAttribute(owner, name, qualName, meta)
        this._attributeBuilders.related_field = (owner, name, qualName, meta) => this._initializeRelatedFieldAttribute(owner, name, qualName, meta)
    }

    _initializeFieldAttribute(owner, attributeName, attributeQualName, attributeMetadata) {
        this._fields[attributeName] = createFieldGlue({
            owner: this,
            name: attributeName,
            stateKey: attributeQualName,
            metadata: attributeMetadata,
            existingField: this._fields[attributeName],
        })

        Object.defineProperty(this, attributeName, {
            get() {
                this._ensureLoaded()
                return this._state?.[attributeQualName]?.value
            },
            set(value) {
                this._fields[attributeName].value = value?.__glue__isFieldProxy ? value.value : value
            },
            enumerable: true,
            configurable: true,
        })
    }

    _initializeRelatedFieldAttribute(owner, attributeName, attributeQualName, attributeMetadata) {
        // For related fields with a value, the nested proxy is created by
        // _initializeGlueObjectAttribute when processing the nested policy.
        // The raw FK value (parent_id) is a separate field attribute.
        //
        // For null FKs, there's no nested policy, so we need to define a
        // property that returns null. We only define it if not already set
        // by _initializeGlueObjectAttribute.
        const proxy = this
        const cacheKey = `__glue_object__${this._name}.${attributeQualName}`

        // Only define if not already defined (nested policy case)
        if (!(attributeName in this)) {
            Object.defineProperty(this, attributeName, {
                get() {
                    return proxy[cacheKey] || null
                },
                enumerable: true,
                configurable: true,
            })
        }
    }

}

export default FieldBackedGlueProxy
