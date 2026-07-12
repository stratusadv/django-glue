import BaseGlueProxy from "./base";

/**
 * Proxy for Django forms. Provides field-level property access, validation,
 * save, and foreign-key choice loading. Supports both regular Forms and ModelForms.
 */
class GlueFormProxy extends BaseGlueProxy {
    static choicesCache = new Map();
    /** @type {Object} Reactive field values for Alpine compatibility */

     /**
     * @param {Object} options - Constructor options.
     * @param {GlueHttp} options.http - The HTTP client instance.
     * @param {string} options.name - The unique name of this proxy in the session.
     * @param {Object} options.policy - Proxy policy - immutable and enforces integrity of the proxy.
     * @param {Object} options.state - Proxy state - mutable, dedicated vehicle for state changes in the proxy.
     * @param {Object|null} [options.attributes] - Optional attributes map; falls back to `policy.bound_attributes`.
     * @param {string} options.namespace - Namespace under which this proxy will be accessible in the main Glue instance.
     */
    constructor({http, name, policy, state, attributes = null, namespace = 'form'}) {
        super({http, name, policy, state, attributes, namespace});
        this._pkFieldName = policy.subject_details?.pk_field_name || 'id'
        this._defineFields()
        this._refreshFieldErrorAttributes()
    }

    /**
     * Load instance data from state into reactive field values.
     * Called during construction for child proxies and after bound attribute events complete.
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
        const cacheKey = this._getChoicesCacheKey(fieldName, field);
        const cached = GlueFormProxy.choicesCache.get(cacheKey);

        field.__glue__choicesCacheKey = cacheKey;
        field.__glue__choicesLoaded = Boolean(cached?.loadedFields?.has('__str__'));
        field.__glue__loadingChoices = Boolean(cached?.promise && cached?.pendingFields?.has('__str__'));
        field.__glue__choicesData = cached?.data || [];

        const proxy = this

        Object.defineProperty(field, 'choices',  {
            get: function() {
                proxy._ensureFieldChoices(fieldName, this);
                // Always read from cache to ensure all proxies see the same data
                const cached = GlueFormProxy.choicesCache.get(this.__glue__choicesCacheKey);
                return cached?.data || this.__glue__choicesData;
            },
            enumerable: true,
            configurable: true
        });

        field.buildChoices = function(...choiceFields) {
            return proxy._buildFieldChoices(fieldName, this, choiceFields);
        };

        return field;
    }

    _getChoicesCacheKey(fieldName, field) {
        const subject = this._policy.subject_details || {};
        return field.choices_cache_key
            || [
                subject.model_class_path,
                subject.form_class_path,
                field.choice_model_path,
                fieldName,
            ].filter(Boolean).join(':')
            || `${field.type}:${fieldName}`;
    }

    _ensureFieldChoices(fieldName, field, choiceFields = []) {
        const cacheKey = this._getChoicesCacheKey(fieldName, field);
        const cached = this._getOrCreateChoicesCache(cacheKey, field);
        const requiredFields = this._normalizeChoiceFields(choiceFields);
        const missingFields = requiredFields.filter(choiceField => !cached.loadedFields.has(choiceField));

        if (missingFields.length === 0) {
            this._applyCachedChoicesToField(field, cached);
            return cached.promise || Promise.resolve(cached.data);
        }

        if (cached.promise) {
            field.__glue__loadingChoices = true;
            if (missingFields.every(choiceField => cached.pendingFields.has(choiceField))) {
                return cached.promise;
            }
            return cached.promise.then(() => this._ensureFieldChoices(fieldName, field, choiceFields));
        }

        field.__glue__loadingChoices = true;
        missingFields.forEach(choiceField => cached.pendingFields.add(choiceField));

        const promise = this.foreign_key_choices({
            field_name: fieldName,
            choice_fields: missingFields.filter(choiceField => !['pk', '__str__'].includes(choiceField)),
        }).then(result => {
            const choices = Array.isArray(result) ? result : [];
            this._cacheFieldChoices(fieldName, choices, missingFields);
            return cached.data;
        }).finally(() => {
            missingFields.forEach(choiceField => cached.pendingFields.delete(choiceField));
            cached.promise = null;
            field.__glue__loadingChoices = false;
        });

        cached.promise = promise;
        return promise;
    }

    _buildFieldChoices(fieldName, field, choiceFields = []) {
        this._ensureFieldChoices(fieldName, field, choiceFields);
        const cacheKey = this._getChoicesCacheKey(fieldName, field);
        return GlueFormProxy.choicesCache.get(cacheKey)?.data || [];
    }

    _normalizeChoiceFields(choiceFields = []) {
        return ['pk', '__str__', ...choiceFields].filter((choiceField, index, fields) => {
            return choiceField && fields.indexOf(choiceField) === index;
        });
    }

    _getOrCreateChoicesCache(cacheKey, field) {
        let cached = GlueFormProxy.choicesCache.get(cacheKey);

        if (!cached) {
            cached = {
                data: field.__glue__choicesData || [],
                loadedFields: new Set(),
                pendingFields: new Set(),
                promise: null,
            };
            GlueFormProxy.choicesCache.set(cacheKey, cached);
        }

        return cached;
    }

    _applyCachedChoicesToField(field, cached) {
        field.__glue__choicesLoaded = cached.loadedFields.has('__str__');
        field.__glue__loadingChoices = Boolean(cached.promise);
        field.__glue__choicesData = cached.data;
    }

    _cacheFieldChoices(fieldName, choices, choiceFields = []) {
        const field = this._fields[fieldName];
        if (!field) return;

        const cacheKey = this._getChoicesCacheKey(fieldName, field);
        const cached = this._getOrCreateChoicesCache(cacheKey, field);

        if (Array.isArray(choices)) {
            choices.forEach(choice => this._mergeChoice(cached.data, choice));
        }

        this._normalizeChoiceFields(choiceFields).forEach(choiceField => cached.loadedFields.add(choiceField));
        this._applyCachedChoicesToField(field, cached);
    }

    _mergeChoice(choices, choice) {
        if (!choice || typeof choice !== 'object') return;

        const existing = choices.find(item => item.pk === choice.pk);
        if (existing) {
            Object.assign(existing, choice);
        } else {
            choices.push(choice);
        }
    }

    /**
     * Lazily load choices for a ModelChoiceField.
     * @param {string} fieldName - The field name.
     * @param {Object} field - The field definition object.
     * @returns {Promise<void>}
     * @private
     */
    async _loadFieldChoices(fieldName, field) {
        if (field.__glue__choicesLoaded || field.__glue__loadingChoices) {
            return;
        }
        await this._ensureFieldChoices(fieldName, field);
    }

    /**
     * Update choices array for a field.
     * @param {string} fieldName - The field name.
     * @param {Array} choices - The new choices array.
     * @private
     */
    _setFieldChoices(fieldName, choices, choiceFields = []) {
        const field = this._fields[fieldName];
        if (!field) return;

        this._cacheFieldChoices(fieldName, choices, choiceFields);
    }

    /**
     * Get the primary key value for this model instance.
     * @returns {*} The primary key value, or null/undefined if not set.
     */
    get pk() {
        let pk = this._policy.subject_details.target_pk

        if (!pk) {
            pk = this._state.instance_data?.[this._pkFieldName]
        }

        return pk
    }

    /**
     * Define a property getter/setter on the proxy instance for a given field name,
     * so that `proxy.fieldName` reads/writes `proxy._values[fieldName]`.
     * @param {string} fieldName - The field name.
     * @private
     */
    _defineFieldNameProperty(fieldName, field) {
        field = {...(field || {})}

        if (field.type === 'ModelMultipleChoiceField') {
            if (!this._state.instance_data) {
                this._state.instance_data = {};
            }
            if (this._state.instance_data[fieldName] === undefined || this._state.instance_data[fieldName] === null) {
                this._state.instance_data[fieldName] = [];
            }
        }

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

                return this._state.instance_data[fieldName];
            },
            set: function (value) {
                if (!this._state.instance_data) {
                    this._state.instance_data = {};
                }
                this._state.instance_data[fieldName] = value;
            }
        })

        if (!field.hasOwnProperty('value')) {
            Object.defineProperty(field, 'value', {
                get: function () {
                    return this._state.instance_data[fieldName];
                }.bind(this),
                set: function (val) {
                    if (!this._state.instance_data) this._state.instance_data = {};
                    this._state.instance_data[fieldName] = val;
                }.bind(this)
            });
        }

        if (!field.hasOwnProperty('errors')) {
            Object.defineProperty(field, 'errors', {
                get: function () {
                    return this._state.errors?.[fieldName];
                }.bind(this),
                enumerable: true,
                configurable: true
            });
        }

        // Initialize error attributes (will be refreshed after each event response)
        field.hasErrors = false;
        field.errorText = '';

        this._fields[fieldName] = field;
        this._fields[fieldName]['name'] = fieldName;
    }

    /**
     * Define all field properties and field metadata on the proxy instance.
     * @private
     */
    _defineFields() {
        this._fields = {}
        this._fields[this.pkFieldName] = this.pk

        Object.keys(this._fields).forEach(k => delete this._fields[k]);

        Object.entries(this._policy.subject_details.included_fields).forEach(([fieldName, field]) => {
            if (!this.hasOwnProperty(fieldName)) {
                this._defineFieldNameProperty(fieldName, field)
            }
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
     * Refresh reactive error attributes on all fields.
     * This mutates actual properties to trigger Alpine reactivity.
     * @private
     */
    _refreshFieldErrorAttributes() {
        Object.keys(this._fields).forEach(fieldName => {
            const field = this._fields[fieldName];
            // Mutate actual properties to trigger Alpine reactivity
            field.hasErrors = this._state?.errors?.[fieldName]?.length > 0;
            field.errorText = this._state?.errors?.[fieldName]?.join(', ');
        });
    }

    /**
     * Check whether the form (or a specific field) has validation errors.
     * @param {string|null} [fieldName] - Optional field name to check.
     * @returns {boolean} True if errors exist.
     */
    hasErrors(fieldName) {
        if (fieldName) {
            return Boolean(this._state?.errors?.[fieldName] && this._state.errors[fieldName].length > 0);
        }

        return Object.keys(this._state?.errors || {}).length > 0;
    }

    _handleEventResponse(attributeName, eventKwargs, response) {
        super._handleEventResponse(attributeName, eventKwargs, response);

        if (attributeName.endsWith('foreign_key_choices') && eventKwargs?.field_name) {
            const fieldName = eventKwargs.field_name;
            this._setFieldChoices(fieldName, response.result, eventKwargs.choice_fields || []);
        }

        // Refresh error attributes to trigger Alpine reactivity
        this._refreshFieldErrorAttributes();

        // Only load instance data from server if there are no errors.
        // When errors exist, preserve user's input so they can correct it.
        if (!this.hasErrors()) {
            this.loadInstanceData();
        }
    }

}

export default GlueFormProxy;
