export class GlueFieldProxy extends BaseGlueProxy {
    constructor({
        proxyUniqueName,
        contextData,
        actions= null,
        fieldName,

    }) {
        super({proxyUniqueName, contextData, actions})

        this.fieldName = fieldName

        Object.keys(this.contextData).forEach(propertyName => {
            this[propertyName] = contextData[propertyName]

            if (this.type === "ForeignKey") {
                Object.defineProperty(this, 'choices', {
                    get: function() {
                        if (!this._choices && !this.loadingChoices) {
                            this.processAction('choices', {fieldName}).then(data => {
                                this._choices = data;
                            }).finally(() => {
                                this.loadingChoices = false
                            });
                        }

                        return this._choices
                    }
                })
            }
        })
    }
}
