import { BaseGlueProxy } from "./base";

export class GlueFormProxy extends BaseGlueProxy {
    constructor({proxyUniqueName, contextData, actions=null}) {
        super({proxyUniqueName, contextData, actions});
        this.fields = contextData.fields;
        this.values = {...contextData.initial};
        this.errors = {};
    }

    postInit() {
        Object.keys(this.fields).forEach(fieldName => {
            Object.defineProperty(this, fieldName, {
                get: () => this.values[fieldName],
                set: (value) => {
                    this.values[fieldName] = value;
                }
            });
        });
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
