import { BaseGlueAdapter } from "./base";

export class ModelGlueAdapter extends BaseGlueAdapter {
    // TODO: Clean this up
    postInit() {
        Object.keys(this.contextData.fields).forEach(fieldName => {
            Object.defineProperty(this, fieldName, {
                get: function() {
                    if (!this.loaded) {
                        if (!this.loading) {
                            this.loading = true;
                            this.get().then(data => {
                                this.values = data;
                            }).finally(() => {
                                this.loading = false;
                                this.loaded = true;
                            });
                        }
                    }

                    return this.values?.[fieldName];
                },
                set: function(value) {
                    if (!this.values) {
                        this.values = {};
                    }
                    this.values[fieldName] = value;

                    this.setActionPayload('save', this.values)
                }
            })
        })
    }
}