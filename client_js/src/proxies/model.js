import { BaseGlueProxy } from "./base";

export class GlueModelProxy extends BaseGlueProxy {
    constructor({
        proxyUniqueName,
        contextData,
        actions=null,
        autoFetch=false,
        values=null
    }) {
        super({proxyUniqueName, contextData, actions, autoFetch});
        this.values = values
        this.#defineFieldsMeta()

        if (this.autoFetch && !this.values) {
            this.loadData()
        }

        this.#defineFieldsAsProperties()
    }

    #defineFieldsMeta() {
        this.fields = {}
        Object.entries(this.contextData.fields).forEach(([fieldName, fieldData]) => {
            // Create a shallow copy for instance-specific properties
            const field = {...fieldData};

            if (field.type === "ForeignKey") {
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

                field.choices = async function() {
                    if (!fieldData._choicesLoaded) {
                        await _choicesAction();
                    }
                    return fieldData._choicesCache;
                }
            }

            this.fields[fieldName] = field
        })
    }

    #defineFieldsAsProperties() {
        Object.keys(this.contextData.fields).forEach(fieldName => {
            Object.defineProperty(this, fieldName, {
                get: function() {
                    if (!this.loaded && !this.autoFetch && !this.values) {
                        if (!this.loading) {
                            this.loading = true;
                            this.loadData()
                        }
                    }

                    return this.values?.[fieldName];
                },
                set: function(value) {
                    if (!this.values) {
                        this.values = {};
                    }
                    this.values[fieldName] = value;
                }
            })
        })
    }

    loadData() {
        this.processAction('get').then(data => {
            this.values = data;
        }).finally(() => {
            this.loading = false;
            this.loaded = true;
        });
    }

    async save() {
        const result = await this.processAction('save', this.values);
        this.values = result;
        return result;
    }

    async delete() {
        return await this.processAction('delete', {id: this.values.id});
    }
}