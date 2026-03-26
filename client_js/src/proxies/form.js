import { BaseGlueProxy } from "./base";
import {snakeToPascal} from "../utils";

export class GlueFormProxy extends BaseGlueProxy {
    constructor({proxyUniqueName, contextData, actions=null}) {
        super({proxyUniqueName, contextData, actions});

        this.$values = {...(this.$contextData.initial || {})};
        this.$errors = {};

        this.$defineFields()
    }

    __defineModelChoiceField(fieldName, fieldData) {
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
            fieldData.__glue__choicesPromise = this.$processAction('foreign_key_choices', {
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

    $defineFields() {
        this.$fields = {}
        Object.entries(this.$contextData.fields).forEach(([fieldName, fieldData]) => {
            Object.defineProperty(this, fieldName, {
                get: function() {
                    if (!this.$loaded && !this.$values) {
                        if (!this.$loading) {
                            this.$loading = true;
                            this.get()
                        }
                    }

                    return this.$values?.[fieldName];
                },
                set: function(value) {
                    if (!this.$values) {
                        this.$values = {};
                    }
                    this.$values[fieldName] = value;
                }
            })

            if (["ModelChoiceField", "ModelMultipleChoiceField"].includes(fieldData.type)) {
                fieldData = this.__defineModelChoiceField(fieldName, fieldData)
            }

            this.$fields[fieldName] = fieldData;
            Object.keys(this.$fields[fieldName]).forEach(attributeName => {
                this[`${fieldName}${snakeToPascal(attributeName)}`] = this.$fields?.[fieldName]?.[attributeName]
                this.$updateErrorAttributesForField(fieldName)
            })
        })
    }

    get(pk = null) {
        this.$processAction('get').then(data => {
            this.$values = data
        }).finally(() => {
            this.$loading = false;
            this.$loaded = true;
        });
    }

    $updateErrorAttributesForField(fieldName) {
        this[`${fieldName}HasErrors`] = this.$errors[fieldName]?.length > 0;
        this[`${fieldName}ErrorText`] = this.$errors[fieldName]?.join(', ');
    }

    $updateErrors(errors) {
        this.$errors = errors || {};
        Object.keys(this.$fields).forEach(fieldName => {
            this.$updateErrorAttributesForField(fieldName);
        });
    }

    $getFormData() {
        const formData = new FormData();
        Object.entries(this.$values).forEach(([fieldName, value]) => {
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
        const result = await this.$processAction('validate', this.$values);
        this.$errors = result.errors || {};

        return result;
    }

    async save() {
        const result = await this.$processAction('save', this.$getFormData());

        this.$updateErrors(result.errors)

        if (result.success) {
            this.$clearErrors()
            this.get(this.$values.id)
        }

        return result;
    }

    hasErrors(fieldName) {
        if (fieldName) {
            return this.$errors[fieldName] && this.$errors[fieldName].length > 0;
        }

        return Object.keys(this.$errors).length > 0;
    }

    $clearErrors() {
        this.$errors = {};
    }
}