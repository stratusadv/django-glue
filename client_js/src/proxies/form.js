import BaseGlueProxy from "./base";

/**
 * Proxy for Django forms. Provides field-level property access, validation,
 * save, and foreign-key choice loading. Supports both regular Forms and ModelForms.
 */
class GlueFormProxy extends BaseGlueProxy {
    /** @type {Object} Reactive field values for Alpine compatibility */
    _values = {};

    /**
     * @param {Object} options - Constructor options.
     * @param {GlueHttp} options.http - The HTTP client instance.
     * @param {string} options.name - The unique name of this proxy in the session.
     * @param {Object} options.contract - Proxy contract - immutable and enforces integrity of the proxy.
     * @param {Object} options.state - Proxy state - mutable, dedicated vehicle for state changes in the proxy.
     * @param {Object|null} [options.actions] - Optional actions map; falls back to `contract.actions`.
     * @param {string} options.namespace - Namespace under which this proxy will be accessible in the main Glue instance.
     */
    constructor({http, name, contract, state, actions = null, namespace = 'form'}) {
        super({http, name, contract, state, actions, namespace});
        this._defineFields()
    }

    /**
     * Load instance data from state into reactive field values.
     * Called during construction for child proxies and after actions complete.
     */
    loadInstanceData() {
        if (this._state?.instance_data) {
            this._loaded = true;
            for (const fieldName of Object.keys(this._fields)) {
                this[fieldName] = this._state.instance_data[fieldName];
                this._fields[fieldName].value = this._state.instance_data[fieldName];
            }
        }
    }

    /**
     * Attach lazy-loading choices to a ModelChoiceField or ModelMultipleChoiceField.
     * @param {string} fieldName - The field name.
     * @param {Object} field - The field definition object.
     * @returns {Object} The updated fieldData with a `choices` async accessor.
     * @private
     */
    _defineModelChoiceField(fieldName, field) {
        field.__glue__choicesLoaded = false;
        field.__glue__loadingChoices = false;
        field.__glue__choicesCache = [];

        const proxy = this

        Object.defineProperty(field, 'choices', {
            get: async function() {
                if (!field.__glue__choicesLoaded && !field.__glue__loadingChoices) {
                    field.__glue__loadingChoices = true;
                    const response = await proxy._processAction('GlueFormProxy.foreign_key_choices', { field_name: fieldName });
                    field.choices = response.response_payload;
                    field.__glue__choicesLoaded = true;
                    field.__glue__loadingChoices = false;
                }
                return field.__glue__choicesCache;
            },
            set: function (value) {
                field.__glue__choicesCache = value;
                field.__glue__choicesLoaded = true;
            },
            configurable: true
        });

        return field;
    }

    /**
     * Define a property getter/setter on the proxy instance for a given field name,
     * so that `proxy.fieldName` reads/writes `proxy._values[fieldName]`.
     * @param {string} fieldName - The field name.
     * @private
     */
    _defineFieldNameProperty(fieldName, field) {
        field = {...field}

        if (["ModelChoiceField", "ModelMultipleChoiceField"].includes(field.type)) {
            field = this._defineModelChoiceField(fieldName, field)
        }

        Object.defineProperty(this, fieldName, {
            get: function () {
                if (!this._loaded && !this._state.instance_data) {
                    if (!this._loading) {
                        this._loading = true;
                        this.load().then(() => {
                            this.loadInstanceData()
                            this._loading = false;
                        })
                    }
                }

                return this._values[fieldName];
            },
            set: function (value) {
                this._values[fieldName] = value;
                if (!this._state.instance_data) {
                    this._state.instance_data = {};
                }
                this._state.instance_data[fieldName] = value;
            }
        })

        if (!field.hasOwnProperty('value')) {
            Object.defineProperty(field, 'value', {
                get: function () {
                    return this._values[fieldName];
                }.bind(this),
                set: function (val) {
                    this._values[fieldName] = val;
                    if (!this._state.instance_data) this._state.instance_data = {};
                    this._state.instance_data[fieldName] = val;
                }.bind(this)
            });
        }

        if (!field.hasOwnProperty('errors')) {
            Object.defineProperty(field, 'errors', {
                get: function () {
                    return this._state._errors?.[fieldName];
                }.bind(this),
            });
        }

        this._fields[fieldName] = field;
        this._fields[fieldName]['name'] = fieldName;
    }

    /**
     * Define all field properties and field metadata on the proxy instance.
     * @private
     */
    _defineFields() {
        this._fields = {}

        Object.keys(this._fields).forEach(k => delete this._fields[k]);
        Object.entries(this._contract.custom_data.allowed_fields).forEach(([fieldName, field]) => {
            if (!this.hasOwnProperty(fieldName)) {
                this._defineFieldNameProperty(fieldName, field)
            }

            Object.keys(this._fields[fieldName]).forEach(attributeName => {
                this._updateErrorAttributesForField(fieldName)
            })
        })

        if (!this.hasOwnProperty('$fields')) {
            Object.defineProperty(this, '$fields', {
                get: function() {
                    return this._fields
                },
                set: value => {
                    this._fields = value
                },
            })
        }
    }

    /**
     * Update has_errors and error_text attributes for a field.
     * @param {string} fieldName - The field name.
     * @private
     */
    _updateErrorAttributesForField(fieldName) {
        this._fields[fieldName][`has_errors`] = this._state._errors?.[fieldName]?.length > 0;
        this._fields[fieldName][`error_text`] = this._state._errors?.[fieldName]?.join(', ');
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

    _handleActionResponse(actionName, actionKwargs, response) {
        // this.loadInstanceData();

        // if (actionName === 'foreign_key_choices' && actionKwargs?.field_name) {
        //     const fieldName = actionKwargs.field_name;
        //     this._fields[fieldName].choices = response.response_payload;
        //     this._fields[fieldName].__glue__choicesLoaded = true;
        // }
    }
}

export default GlueFormProxy;
