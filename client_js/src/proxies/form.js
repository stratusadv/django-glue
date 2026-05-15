import { BaseGlueProxy } from "./base";
import {snakeToPascal} from "../utils";

export class GlueFormProxy extends BaseGlueProxy {
    static name = 'form'

    constructor({http, proxyUniqueName, contextData, actions=null}) {
        super({http, proxyUniqueName, contextData, actions});

        this._values = {...(this._contextData.initial || {})};

        this._errors = {};

        this._defineFields()

        Object.defineProperty(this,'$fields', {
            get: () => { return this._fields },
            set: value => { this._fields = value },
        })

    }

    _defineModelChoiceField(fieldName, fieldData) {
        // Initialize shared choice caching on the original fieldData (once)
        // This ensures choices are loaded only once across all model proxy instances
        if (!fieldData.hasOwnProperty('__choicesCache')) {
            fieldData.__glue__choicesCache = [];
            fieldData.__glue__choicesLoaded = false;
            fieldData.__glue__loadingChoices = false;
            fieldData.__glue__choicesPromise = null;
        }

        const choicesAction = async function() {
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
                fieldData._choicesLoaded = true;
                return data;
            }).finally(() => {
                fieldData.__glue__loadingChoices = false;
            });

            return fieldData.__glue__choicesPromise;
        }.bind(this)

        this[`${fieldName}Choices`] = async function() {
            if (!fieldData._choicesLoaded) {
                await choicesAction();
            }
            return fieldData.__glue__choicesCache;
        }

        return fieldData
    }

    _defineFieldNameProperty(fieldName) {
        Object.defineProperty(this, fieldName, {
            get: function() {
                if (!this._loaded && !this._values) {
                    if (!this._loading) {
                        this._loading = true;
                        this.get()
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
    }

    _defineFields() {
        this._fields = {}
        Object.entries(this._contextData.fields).forEach(([fieldName, fieldData]) => {
            this._defineFieldNameProperty(fieldName)

            if (["ModelChoiceField", "ModelMultipleChoiceField"].includes(fieldData.type)) {
                fieldData = this._defineModelChoiceField(fieldName, fieldData)
            }

            this._fields[fieldName] = fieldData;
            Object.keys(this._fields[fieldName]).forEach(attributeName => {
                this[`${fieldName}${snakeToPascal(attributeName)}`] = this._fields?.[fieldName]?.[attributeName]
                this._updateErrorAttributesForField(fieldName)
            })
        })
    }

    get(pk = null) {
        this._processAction('get').then(data => {
            this._values = data
        }).finally(() => {
            this._loading = false;
            this._loaded = true;
        });
    }

    _updateErrorAttributesForField(fieldName) {
        this[`${fieldName}HasErrors`] = this._errors[fieldName]?.length > 0;
        this[`${fieldName}ErrorText`] = this._errors[fieldName]?.join(', ');
    }

    _updateErrors(errors) {
        this._errors = errors || {};
        Object.keys(this._fields).forEach(fieldName => {
            this._updateErrorAttributesForField(fieldName);
        });
    }

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

    async validate() {
        const result = await this._processAction('validate', this._values);
        this._errors = result.errors || {};

        return result;
    }

    async save() {
        const result = await this._processAction('save', this._getFormData());

        this._updateErrors(result.errors)

        if (result.success) {
            this._clearErrors()
            this.get(this._values.id)
        }

        return result;
    }

    hasErrors(fieldName) {
        if (fieldName) {
            return this._errors[fieldName] && this._errors[fieldName].length > 0;
        }

        return Object.keys(this._errors).length > 0;
    }

    _clearErrors() {
        this._errors = {};
    }
}