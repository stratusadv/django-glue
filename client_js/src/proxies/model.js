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
    /**
     * @param {Object} options - Constructor options.
     * @param {GlueHttp} options.http - The HTTP client instance.
     * @param {string} options.name - The unique name of this proxy in the session.
     * @param {Object} options.contract - Proxy contract - immutable and enforces integrity of the proxy.
     * @param {Object} options.state - Proxy state - mutable, dedicated vehicle for state changes in the proxy.
     * @param {Object|null} [options.actions] - Optional actions map; falls back to `contract.actions`.
     * @param {string} options.namespace - Namespace under which this proxy will be accessible in the main Glue instance.
     * @param {boolean} [options.autoFetch] - Whether to auto-fetch on first access.
     * @param {GlueQuerySetProxy|null} [options.parentQuerySet] - Parent queryset proxy, if any.
     */

    constructor({
        http,
        name,
        contract,
        state,
        actions = null,
        autoFetch = false,
        parentQuerySet = null,
        namespace = 'model'
    }) {
        super({http, name, contract, state, actions, autoFetch, namespace});

        if (this._state.instance_data) {
            this._defineExtraFields()
            this.loadInstanceData()
        }

        /** @type {string} */
        this.$key = `django-glue-${++_keyCounter}`
        /** @type {GlueQuerySetProxy|null} */
        this._parent = parentQuerySet
        /** @type {string} */
        this._pkFieldName = contract.custom_data?.pk_field_name || 'id'
    }

    /**
     * Get the primary key value for this model instance.
     * @returns {*} The primary key value, or null/undefined if not set.
     */
    get pk() {
        let pk = this._contract.custom_data.target_pk

        if (!pk) {
            pk = this._state.instance_data?.[this._pkFieldName]
        }

        return pk
    }

    /**
     * Define property accessors for fields that come from outside the regular
     * field definition pipeline (e.g., queryset annotations).
     * @private
     */
    _defineExtraFields() {
        // This will define properties for fields coming from outside the regular field definition pipeline in
        // such as glue queryset annotations, etc.
        Object.keys(this._state.instance_data).forEach(fieldName => {
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
     * Handle state updates after actions complete.
     * Refreshes the parent queryset if this model proxy is a child.
     * @private
     */
    _handleActionResponse(actionName, actionKwargs, response) {
        super._handleActionResponse(actionName, actionKwargs, response);

        if (this._state.instance_data) {
            this._defineExtraFields();
            for (const fieldName of Object.keys(this._state.instance_data)) {
                if (!(fieldName in this._fields)) {
                    this[fieldName] = this._state.instance_data[fieldName];
                }
            }
        }

        if (this._parent) {
            this._parent.refresh();
        }
    }
}

export default GlueModelProxy;
