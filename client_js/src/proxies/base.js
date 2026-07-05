/**
 * Base proxy class. Provides the listener/event system and the core
 * `_processAction` method that all proxy types use to invoke server-side actions.
 */
class BaseGlueProxy {
    /** @type {string} */
    static name = 'baseGlueProxy'

    /**
     * @param {Object} options - Constructor options.
     * @param {GlueHttp} options.http - The HTTP client instance.
     * @param {string} options.uniqueName - The unique name of this proxy in the session.
     * @param {Object} options.contract - Serialized proxy metadata from the server.
     * @param {Object|null} [options.actions] - Optional actions map; falls back to `contract.actions`.
     */
    constructor({http, uniqueName, contract, actions = null}) {
        /** @type {GlueHttp} */
        this.http = http
        /** @type {string} */
        this._uniqueName = uniqueName;
        /** @type {Object} */
        this._contract = contract;
        /** @type {Object} */
        this._actions = !!actions ? actions : contract.actions;

        this._defineCustomActions()

        /**
         * @type {Object<string, Object<string, Function[]>>}
         */
        this._listeners = {
            before: {},
            after: {},
            error: {}
        }

    }

    /**
     * Add a listener for an action.
     * @param {string} actionName - The action to listen for (e.g., 'save', 'delete')
     * @param {Function} callback - The callback function
     * @param {string} [type='after'] - When to call: 'before', 'after' (default), or 'error'
     * @returns {this} The proxy instance for chaining.
     */
    addListener(actionName, callback, type = 'after') {
        if (!this._listeners[type]) {
            throw new Error(`Invalid listener type: _${type}. Use 'before', 'after', or 'error'.`);
        }
        if (!this._listeners[type][actionName]) {
            this._listeners[type][actionName] = [];
        }
        this._listeners[type][actionName].push(callback);
        return this;
    }

    /**
     * Remove a listener for an action.
     * @param {string} actionName - The action name
     * @param {Function} callback - The callback to remove
     * @param {string} [type='after'] - The listener type: 'before', 'after' (default), or 'error'
     * @returns {this} The proxy instance for chaining.
     */
    removeListener(actionName, callback, type = 'after') {
        const listeners = this._listeners[type]?.[actionName];
        if (listeners) {
            const index = listeners.indexOf(callback);
            if (index > -1) {
                listeners.splice(index, 1);
            }
        }
        return this;
    }

    /**
     * Remove all registered listeners.
     * @returns {this} The proxy instance for chaining.
     */
    clearListeners() {
        this._listeners = {};
        return this;
    }

    /**
     * Emit listeners for a given action and event type.
     * @param {string} type - Listener type: 'before', 'after', or 'error'.
     * @param {string} actionName - The action name.
     * @param {Object} event - The event payload.
     * @private
     */
    async emitListeners(type, actionName, event) {
        const listeners = this._listeners[type]?.[actionName] || [];
        for (const callback of listeners) {
            await callback(event);
        }
    }

    /**
     * Execute a server-side action, emitting before/after/error listeners.
     * @param {string} actionName - The action method name.
     * @param {Object|null} [actionKwargs] - Action-specific user data (e.g., step number, filter params).
     * @param {Object|null} [state] - Proxy-intrinsic runtime state (e.g., form_values, instance_pk).
     *                                    Files in proxyState are automatically extracted and sent via FormData.
     * @returns {Promise<Object>} The server response data.
     * @private
     */
    async _processAction(actionName, actionKwargs = null, state = null) {
        const event = {
            action: actionName,
            proxy: this,
            actionKwargs: actionKwargs,
        };

        // Emit 'before' listeners
        await this.emitListeners('before', actionName, event);

        try {
            const response = await this.http.sendActionRequest({
                uniqueName: this._uniqueName,
                action: actionName,
                actionKwargs: actionKwargs,
                contract: this._contract,  // Never modified - signature verified server-side
                state,  // Proxy-intrinsic runtime state (not signed)
            });

            // Handle response state (e.g., form errors, updated values)
            const responseData = response.data;
            if (responseData.state) {
                this._updateState(responseData.state);
            }

            // Extract the actual data (may be wrapped or direct)
            const data = responseData.data !== undefined ? responseData.data : responseData;
            event.result = data;

            // Emit 'after' listeners
            await this.emitListeners('after', actionName, event);

            return data;
        } catch (err) {
            event.error = err;

            // Emit 'error' listeners
            await this.emitListeners('error', actionName, event);

            throw err;
        }
    }

    /**
     * Handle proxy_state from server response.
     * Override in subclasses to handle proxy-specific state updates.
     * @param {Object} state - Proxy-intrinsic state from the server.
     * @protected
     */
    _updateState(state) {
        // Base implementation does nothing - override in subclasses
    }

    async _defaultProcessAction(actionName, actionKwargs = null, state = null) {
        return await this._processAction(actionName, actionKwargs, state)
    }

    _defineCustomActions() {
        Object.keys(this._actions).forEach(actionName => {
            if (!(actionName in this)) {
                this[actionName] = async (actionKwargs = null) => {
                    return await this._defaultProcessAction(actionName, actionKwargs)
                }
            }
        })
    }
}

export default BaseGlueProxy;
