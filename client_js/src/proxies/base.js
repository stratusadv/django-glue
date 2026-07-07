/**
 * Base proxy class. Provides the listener/event system and the core
 * action invocation mechanism that all proxy types use to invoke server-side actions.
 */
class BaseGlueProxy {
    /** @type {boolean} */
    _loaded = false;
    /** @type {boolean} */
    _loading = false;

    /**
     * @param {Object} options - Constructor options.
     * @param {GlueHttp} options.http - The HTTP client instance.
     * @param {string} options.name - The unique name of this proxy in the session.
     * @param {Object} options.contract - Proxy contract - immutable and enforces integrity of the proxy.
     * @param {Object} options.state - Proxy state - mutable, dedicated vehicle for state changes in the proxy.
     * @param {Object|null} [options.actions] - Optional actions map; falls back to `contract.actions`.
     * @param {string} options.namespace - Namespace under which this proxy will be accessible in the main Glue instance.
     */
    constructor({http, name, contract, state = null, actions = null, namespace = 'base'}) {
        /** @type {GlueHttp} */
        this.http = http
        /** @type {string} */
        this._namespace = namespace
        /** @type {string} */
        this._name = name;
        /** @type {Object} */
        this._contract = contract;
        /** @type {Object} */
        this._state = state;
        /** @type {Object} */
        this._actions = !!actions ? actions : contract.actions;

        this._defineDefaultActions()

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
     */
    async emitListeners(type, actionName, event) {
        const listeners = this._listeners?.[type]?.[actionName] || [];
        for (const callback of listeners) {
            await callback(event);
        }
    }

    /**
     * Execute a server-side action, emitting before/after/error listeners.
     * @param {string} actionName - The action method name.
     * @param {Object|null} [actionKwargs] - Action-specific user data.
     * @returns {Promise<Object>} The server response data.
     * @private
     */
    async _processAction(actionName, actionKwargs = null) {
        const event = {
            action: actionName,
            proxy: this,
            actionKwargs,
        };

        await this.emitListeners('before', actionName, event);

        this._loading = true;

        try {
            const response = await this.http.sendActionRequest({
                name: this._name,
                action: actionName,
                actionKwargs,
                contract: this._contract,
                state: this._state,
            });

            const responseData = response.data;

            // Mutate _state in place so Alpine's Proxy keeps the same reference
            if (this._state) {
                Object.assign(this._state, responseData.state);
            } else {
                this._state = responseData.state;
            }

            this._handleActionResponse(actionName, actionKwargs, responseData);

            // Extract the actual data (may be wrapped or direct)
            const data = responseData.data !== undefined ? responseData.data : responseData;
            event.result = data;

            await this.emitListeners('after', actionName, event);

            return data;
        } catch (err) {
            event.error = err;

            await this.emitListeners('error', actionName, event);

            throw err;
        } finally {
            this._loading = false;
        }
    }

    _handleActionResponse(actionName, actionKwargs, response) {}

    _defineDefaultActions() {
        Object.entries(this._actions).forEach(([actionKey, action]) => {
            const [actionProvider, actionName] = actionKey.split('.').slice(0, 2)
            const accessPath = action.client_proxy_access_path
            const accessPathParts = accessPath ? [accessPath.split('.'), ''] : ['']

            let propertyTarget = this
            accessPathParts.forEach(pathPart => {
                if (pathPart) {
                    propertyTarget[pathPart] = {
                        _processAction: this._processAction.bind(this),
                    }
                    propertyTarget = propertyTarget[pathPart]
                }

                if (!(actionName in propertyTarget)) {
                    Object.defineProperty(propertyTarget, actionName, {
                        get: function () {
                            return async (actionKwargs = null) => {
                                debugger
                                return await this._processAction(actionKey, actionKwargs);
                            };
                        },
                        enumerable: true,
                        configurable: true
                    });
                }
            })
        });
    }
}

export default BaseGlueProxy;
