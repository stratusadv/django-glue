import BaseGlueProxy from "./base";

/**
 * Proxy for Django forms. Provides field-level property access, validation,
 * save, and foreign-key choice loading. Supports both regular Forms and ModelForms.
 */
class GlueFormProxy extends BaseGlueProxy {
    /** @type {string} */
    static name = 'form'

    /**
     * @param {Object} options - Constructor options.
     * @param {GlueHttp} options.http - The HTTP client instance.
     * @param {string} options.proxyUniqueName - The unique name of this proxy.
     * @param {Object} options.contextData - Serialized proxy metadata from the server.
     * @param {Object|null} [options.actions] - Optional actions map.
     */
    constructor({http, proxyUniqueName, contextData, actions = null}) {
        super({http, proxyUniqueName, contextData, actions});

        /** @type {Object} */
        this._values = {...(this._contextData.initial || {})};

        /** @type {Object} */
        this._errors = {};

        this._defineFields()

        Object.defineProperty(this, '$fields', {
            get: () => {
                return this._fields
            },
            set: value => {
                this._fields = value
            },
        })

    }

    /**
     * Attach lazy-loading choices to a ModelChoiceField or ModelMultipleChoiceField.
     * @param {string} fieldName - The field name.
     * @param {Object} fieldData - The field definition object.
     * @returns {Object} The updated fieldData with a `choices` async accessor.
     * @private
     */
    _defineModelChoiceField(fieldName, fieldData) {
        // Initialize shared choice caching on the original fieldData (once)
        // This ensures choices are loaded only once across all model proxy instances
        if (!fieldData.hasOwnProperty('__choicesCache')) {
            fieldData.__glue__choicesCache = [];
            fieldData.__glue__choicesLoaded = false;
            fieldData.__glue__loadingChoices = false;
            fieldData.__glue__choicesPromise = null;
        }

        const choicesAction = async function () {
            // If already loading, return the existing promise to avoid duplicate requests
            if (fieldData.__glue__choicesPromise) {
                return fieldData.__glue__choicesPromise;
            }

            fieldData.__glue__loadingChoices = true;
            fieldData.__glue__choicesPromise = this._processAction('foreign_key_choices', {
                'field_definition': [
                    fieldName,
                    fieldData
                ]
            }).then(data => {
                fieldData.__glue__choicesCache = data;
                fieldData.__glue__choicesLoaded = true;
                return data;
            }).finally(() => {
                fieldData.__glue__loadingChoices = false;
            });

            return fieldData.__glue__choicesPromise;
        }.bind(this)

        fieldData.choices = async function () {
            if (!fieldData.__glue__choicesLoaded) {
                await choicesAction();
            }
            return fieldData.__glue__choicesCache;
        }

        return fieldData
    }

    /**
     * Define a property getter/setter on the proxy instance for a given field name,
     * so that `proxy.fieldName` reads/writes `proxy._values[fieldName]`.
     * @param {string} fieldName - The field name.
     * @private
     */
    _defineFieldNameProperty(fieldName) {
        Object.defineProperty(this, fieldName, {
            get: function () {
                if (!this._loaded && !this._values) {
                    if (!this._loading) {
                        this._loading = true;
                        this.get()
                    }
                }

                return this._values?.[fieldName];
            },
            set: function (value) {
                if (!this._values) {
                    this._values = {};
                }
                this._values[fieldName] = value;
            }
        })
    }

    /**
     * Define all field properties and field metadata on the proxy instance.
     * @private
     */
    _defineFields() {
        this._fields = {}
        Object.entries(this._contextData.fields).forEach(([fieldName, fieldData]) => {
            this._defineFieldNameProperty(fieldName)

            // Clone fieldData so each proxy instance owns its own copy,
            // avoiding shared references that cause bound getters to overwrite each other
            fieldData = {...fieldData}

            if (["ModelChoiceField", "ModelMultipleChoiceField"].includes(fieldData.type)) {
                fieldData = this._defineModelChoiceField(fieldName, fieldData)
            }

            this._fields[fieldName] = fieldData;
            this._fields[fieldName]['name'] = fieldName;

            if (!fieldData.hasOwnProperty('value')) {
                Object.defineProperty(fieldData, 'value', {
                    get: function () {
                        return this._values?.[fieldName];
                    }.bind(this),
                    set: function (val) {
                        if (!this._values) this._values = {};
                        this._values[fieldName] = val;
                    }.bind(this)
                });
            }

            if (!fieldData.hasOwnProperty('errors')) {
                Object.defineProperty(fieldData, 'errors', {
                    get: function () {
                        return this._errors?.[fieldName];
                    }.bind(this),
                });
            }

            Object.keys(this._fields[fieldName]).forEach(attributeName => {
                this._updateErrorAttributesForField(fieldName)
            })

        })
    }

    /**
     * Fetch current field values from the server.
     * @param {string|null} [pk] - Optional primary key to fetch.
     * @returns {Promise<Object>} The fetched field values.
     */
    async get(pk = null) {
        const data = await this._processAction('get');
        this._values = data;
        this._loading = false;
        this._loaded = true;
        return data;
    }

    /**
     * Update has_errors and error_text attributes for a field.
     * @param {string} fieldName - The field name.
     * @private
     */
    _updateErrorAttributesForField(fieldName) {
        this._fields[fieldName][`has_errors`] = this._errors[fieldName]?.length > 0;
        this._fields[fieldName][`error_text`] = this._errors[fieldName]?.join(', ');
    }

    /**
     * Update error state for all fields.
     * @param {Object} errors - Error mapping from the server.
     * @private
     */
    _updateErrors(errors) {
        this._errors = errors || {};
        Object.keys(this._fields).forEach(fieldName => {
            this._updateErrorAttributesForField(fieldName);
        });
    }

    /**
     * Build a FormData object from the current field values, handling arrays,
     * files, blobs, and null values.
     * @returns {FormData} The constructed FormData.
     * @private
     */
    _getFormData() {
        const formData = new FormData();
        Object.entries(this._values).forEach(([fieldName, value]) => {
            if (Array.isArray(value)) {
                value.forEach(item => formData.append(fieldName, item));
            } else if (value instanceof File || value instanceof Blob) {
                formData.append(fieldName, value);
            } else if (value instanceof FileList) {
                Array.from(value).forEach(file => formData.append(fieldName, file));
            } else {
                formData.append(fieldName, value === null || value === undefined ? '' : value);
            }
        });

        return formData;
    }

    /**
     * Validate the current field values against the server.
     * @returns {Promise<Object>} Validation result with `{success, errors, ...}`.
     */
    async validate() {
        const result = await this._processAction('validate', this._values);
        this._errors = result.errors || {};

        return result;
    }

    /**
     * Save the current field values to the server. On success, clears errors
     * and refreshes field data.
     * @returns {Promise<Object>} Save result with `{success, errors, ...}`.
     */
    async save() {
        const result = await this._processAction('save', this._getFormData());

        this._updateErrors(result.errors)

        if (result.success) {
            this._clearErrors()
            this.get(this._values.id)
        }

        return result;
    }

    /**
     * Check whether the form (or a specific field) has validation errors.
     * @param {string|null} [fieldName] - Optional field name to check.
     * @returns {boolean} True if errors exist.
     */
    hasErrors(fieldName) {
        if (fieldName) {
            return Boolean(this._errors[fieldName] && this._errors[fieldName].length > 0);
        }

        return Object.keys(this._errors).length > 0;
    }

    /**
     * Clear all validation errors.
     * @private
     */
    _clearErrors() {
        this._errors = {};
    }
}

export default GlueFormProxy;
