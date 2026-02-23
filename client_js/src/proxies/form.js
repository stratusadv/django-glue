import { BaseGlueProxy } from "./base";

export class GlueFormProxy extends BaseGlueProxy {
    constructor({proxyUniqueName, contextData, actions=null}) {
        super({proxyUniqueName, contextData, actions});
    }

    postInit() {
        this.fields = this.contextData.fields;
        this.values = {...this.contextData.initial};
        this.errors = {};

        Object.keys(this.fields).forEach(fieldName => {
            Object.defineProperty(this, fieldName, {
                get: () => this.values[fieldName],
                set: (value) => {
                    this.values[fieldName] = value;
                }
            });
        });
    }

    async validate() {
        const result = await this.processAction('validate', this.values);
        this.errors = result.errors || {};
        return result;
    }

    async submit() {
        const result = await this.processAction('submit', this.values);
        this.errors = result.errors || {};
        return result;
    }

    getFieldDefinition(fieldName) {
        return this.fields[fieldName] || null;
    }

    getFieldError(fieldName) {
        return this.errors[fieldName] || [];
    }

    hasErrors() {
        return Object.keys(this.errors).length > 0;
    }

    clearErrors() {
        this.errors = {};
    }
}
