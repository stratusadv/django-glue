import GlueFormProxy from "./form";

/**
 * Monotonically increasing counter used to generate unique `$key` values
 * for each model proxy instance.
 */
let _keyCounter = 0;

/**
 * Proxy for a single Django model instance. Extends form proxy with model-specific
 * behavior including lazy loading, deletion, and parent queryset tracking.
 */
class GlueModelProxy extends GlueFormProxy {
    /** @type {string} */
    static name = 'model'

    /**
     * @param {Object} options - Constructor options.
     * @param {GlueHttp} options.http - The HTTP client instance.
     * @param {string} options.proxyUniqueName - The unique name of this proxy.
     * @param {Object} options.contextData - Serialized proxy metadata from the server.
     * @param {Object|null} [options.actions] - Optional actions map.
     * @param {boolean} [options.autoFetch] - Whether to auto-fetch on first access.
     * @param {Object|null} [options.values] - Pre-populated field values (from queryset).
     * @param {GlueQuerySetProxy|null} [options.parentQuerySet] - Parent queryset proxy, if any.
     */
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
        /** @type {Object|null} */
        this._values = values;

        if (values) {
            this._defineExtraFields()
        }

        /** @type {string} */
        this.$key = `django-glue-${++_keyCounter}`
        /** @type {GlueQuerySetProxy|null} */
        this._parent = parentQuerySet
    }

    /**
     * Define property accessors for fields that come from outside the regular
     * field definition pipeline (e.g., queryset annotations).
     * @private
     */
    _defineExtraFields() {
        // This will define properties for fields coming from outside the regular field definition pipeline in
        // such as glue queryset annotations, etc.
        Object.keys(this._values).forEach(fieldName => {
            if (!(fieldName in this)) {
                this._defineFieldNameProperty(fieldName)
            }
        })
    }

    /**
     * Whether this model instance is new (not yet persisted to the database).
     * @type {boolean}
     */
    get _isNew() {
        return !this._values?.id;
    }

    /**
     * Fetch current field values from the server. If the proxy was created from
     * a parent queryset, the request goes through the parent.
     * @returns {Promise<void>}
     */
    async get() {
        let data;
        if (this._parent) {
            data = await this._parent._processAction('get', {id: this._values?.id})
        } else {
            data = await this._processAction('get')
        }

        this._values = data


        this._loading = false;
        this._loaded = true;
    }

    async _defaultProcessAction(actionName) {
        if (this._parent) {
            return await this._parent._processAction(actionName, {id: this._values?.id})
        } else {
            return await this._processAction(actionName)
        }
    }

    /**
     * Delete the model instance on the server. For unsaved instances with a parent
     * queryset, removes the item locally and refreshes the parent.
     * @returns {Promise<Object>} Deletion result.
     */
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
