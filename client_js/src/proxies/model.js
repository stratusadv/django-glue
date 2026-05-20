import GlueFormProxy from "./form";

let _keyCounter = 0;

class GlueModelProxy extends GlueFormProxy {
    static name = 'model'

    constructor({
                    http,
                    proxyUniqueName,
                    contextData,
                    actions = null,
                    autoFetch = false,
                    values = null,
                    parentQuerySet = null
                }) {
        super({http, proxyUniqueName, contextData, actions, autoFetch});
        this._values = values;

        if (values) {
            this._defineExtraFields()
        }

        this.$key = `django-glue-${++_keyCounter}`
        this._parent = parentQuerySet
    }

    _defineExtraFields() {
        // This will define properties for fields coming from outside the regular field definition pipeline in
        // such as glue queryset annotations, etc.
        Object.keys(this._values).forEach(fieldName => {
            if (!(fieldName in this)) {
                this._defineFieldNameProperty(fieldName)
            }
        })
    }

    get _isNew() {
        return !this._values?.id;
    }

    async get(pk = null) {
        let data;
        if (this._parent) {
            data = await this._parent._processAction('get', {id: pk})
        } else {
            data = await this._processAction('get')
        }

        this._values = data


        this._loading = false;
        this._loaded = true;
    }

    async delete() {
        if (this._isNew && this._parent) {
            await this._parent.refresh();
            return {success: true};
        }
        const result = await this._processAction('delete', {id: this._values.id});
        if (this._parent) {
            await this._parent.refresh();
        }
        return result;
    }
}

export default GlueModelProxy;