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
        /** @type {string} */
        this._pkFieldName = contextData.pk_field_name || 'id'
    }

    /**
     * Get the primary key value for this model instance.
     * @returns {*} The primary key value, or null/undefined if not set.
     */
    get _pk() {
        return this._values?.[this._pkFieldName]
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
        return !this._pk;
    }

    /**
     * Fetch current field values from the server. If the proxy was created from
     * a parent queryset, the request goes through the parent.
     * @returns {Promise<void>}
     */
    async get() {
        // instance_pk and parent routing are handled by _processAction override
        const data = await this._processAction('get');
        this._values = data;
        this._loading = false;
        this._loaded = true;
    }

    /**
     * Override _processAction to include instance_pk, form_values, and route through parent if needed.
     * @param {string} actionName - The action method name.
     * @param {Object|null} [userData] - Action-specific user data.
     * @param {Object|null} [proxyData] - Proxy-intrinsic runtime state.
     * @returns {Promise<Object>} The server response data.
     * @private
     */
    async _processAction(actionName, userData = null, proxyData = null) {
        // Always include instance_pk and form_values in proxyData for model instances
        const modelProxyData = {
            ...(proxyData || {}),
            instance_pk: this._pk,
            form_values: this._values || {},
        };

        if (this._parent) {
            // If a model proxy has a parent, route through the parent queryset proxy.
            // The queryset proxy methods need the PK to retrieve the proper model object.
            return await this._parent._processAction(actionName, userData, modelProxyData);
        } else {
            // No parent - use prototype.call to ensure Alpine's proxy observes mutations
            return await GlueFormProxy.prototype._processAction.call(this, actionName, userData, modelProxyData);
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
        // instance_pk is automatically included by _processAction override
        const result = await this._processAction('delete');
        if (this._parent) {
            await this._parent.refresh();
        }
        return result;
    }
}

export default GlueModelProxy;
