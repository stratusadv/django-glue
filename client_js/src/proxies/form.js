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
            // Pass field_definition in user_data for this action
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
     * Override _processAction to include form field values in proxyData.
     * This ensures the backend form instance always has access to accumulated field state.
     * @param {string} actionName - The action method name.
     * @param {Object|null} [userData] - Action-specific user data.
     * @param {Object|null} [proxyData] - Proxy-intrinsic runtime state.
     * @returns {Promise<Object>} The server response data.
     * @private
     */
    async _processAction(actionName, userData = null, proxyData = null) {
        // Always include form_values in proxyData so backend can bind the form
        const formProxyData = {
            ...(proxyData || {}),
            form_values: this._values || {},
        };

        return await BaseGlueProxy.prototype._processAction.call(this, actionName, userData, formProxyData);
    }

    /**
     * Handle proxy_data from server response.
     * Updates form errors and field values from the response.
     * @param {Object} proxyData - Proxy-intrinsic state from the server.
     * @protected
     */
    _handleResponseProxyData(proxyData) {
        if (proxyData.errors) {
            this._updateErrors(proxyData.errors);
        }
        if (proxyData.form_values) {
            this._values = {...this._values, ...proxyData.form_values};
        }
    }

    /**
     * Fetch current field values from the server.
     * @returns {Promise<Object>} The fetched field values.
     */
    async get() {
        const data = await super._processAction('get');
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
     * Validate the current field values against the server.
     * @returns {Promise<Object>} Validation result with `{success, errors, ...}`.
     */
    async validate() {
        const result = await this._processAction('validate');
        this._updateErrors(result.errors);
        return result;
    }

    /**
     * Save the current field values to the server. On success, clears errors
     * and refreshes field data.
     * @returns {Promise<Object>} Save result with `{success, errors, ...}`.
     */
    async save() {
        const result = await this._processAction('save');

        this._updateErrors(result.errors)

        if (result.success) {
            this._clearErrors()
            this.get()
        }

        return result;
    }

    /**
     * Process form with custom logic (e.g., multi-step workflows).
     * @param {Object|null} [userData] - Action-specific user data (e.g., step number).
     * @returns {Promise<Object>} Process result from the server.
     */
    async process(userData = null) {
        const result = await this._processAction('process', userData);
        this._updateErrors(this._errors)

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
