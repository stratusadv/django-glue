import { BaseGlueProxy } from "./base";

export class GlueFormProxy extends BaseGlueProxy {
    constructor({proxyUniqueName, contextData, actions=null}) {
        super({proxyUniqueName, contextData, actions});

        this._values = {...(this.contextData.initial || {})};
        this._errors = {};

        this.#defineFields()
    }

    defineModelChoiceField(fieldName, fieldData) {
        // Initialize shared choice caching on the original fieldData (once)
        // This ensures choices are loaded only once across all model proxy instances
        if (!fieldData.hasOwnProperty('_choicesCache')) {
            fieldData._choicesCache = [];
            fieldData._choicesLoaded = false;
            fieldData._loadingChoices = false;
            fieldData._choicesPromise = null;
        }

        const _choicesAction = async function() {
            // If already loading, return the existing promise to avoid duplicate requests
            if (fieldData._choicesPromise) {
                return fieldData._choicesPromise;
            }

            fieldData._loadingChoices = true;
            fieldData._choicesPromise = this.processAction('foreign_key_choices', {
                'field_definition': [
                    fieldName,
                    fieldData
                ]
            }).then(data => {
                fieldData._choicesCache = data;
                fieldData._choicesLoaded = true;
                return data;
            }).finally(() => {
                fieldData._loadingChoices = false;
            });

            return fieldData._choicesPromise;
        }.bind(this)

        fieldData.choices = async function() {
            if (!fieldData._choicesLoaded) {
                await _choicesAction();
            }
            return fieldData._choicesCache;
        }

        return fieldData
    }

    #defineFields() {
        const proxy = this;

        this.fields = {}
        Object.entries(this.contextData.fields).forEach(([fieldName, fieldData]) => {
            Object.defineProperty(this, fieldName, {
                get: function() {
                    if (!this.loaded && !this.autoFetch && !this._values) {
                        if (!this.loading) {
                            this.loading = true;
                            this.loadData()
                        }
                    }

                    return this._values?.[fieldName];
                },
                set: function(value) {
                    if (!this._values) {
                        this._values = {};
                    }
                    this._values[fieldName] = value;
                }
            })

            if (fieldData.type === "ModelChoiceField") {
                fieldData = this.defineModelChoiceField(fieldName, fieldData)
            }

            this.fields[fieldName] = {
                ...fieldData,
                get value() { return proxy._values[fieldName]; },
                set value(val) { proxy._values[fieldName] = val; },
                get errors() { return proxy._errors[fieldName] || []; }
            };
        })
    }

    loadData() {
        this.processAction('get').then(data => {
            this._values = data;
        }).finally(() => {
            this.loading = false;
            this.loaded = true;
        });
    }

    // Getter for all current values (for submitting)
    get values() {
        return {...this._values};
    }

    // Getter for all current errors
    get errors() {
        return {...this._errors};
    }

    _updateErrors(errors) {
        this._errors = errors || {};
    }

    async validate() {
        const result = await this.processAction('validate', this._values);
        this._updateErrors(result.errors);

        return result;
    }

    async save() {
        const result = await this.processAction('save', this._values);

        this._errors = result.errors || {};

        if (result.success) {
            this._values = result.cleaned_data
        }

        return result;
    }

    hasErrors() {
        return Object.keys(this._errors).length > 0;
    }

    clearErrors() {
        this._errors = {};
    }
}
