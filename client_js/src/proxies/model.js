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
    }

    postInit() {
        if (this.autoFetch && !this.values) {
            this.loadData()
        }

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
        return await this.processAction('delete');
    }
}