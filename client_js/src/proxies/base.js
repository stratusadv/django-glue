/**
 * Base proxy class. Provides the listener/event system and the core
 * bound attribute event mechanism that all proxy types use to invoke server-side attributes.
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
      * @param {Object} options.policy - Proxy policy - immutable and enforces integrity of the proxy.
      * @param {Object} options.state - Proxy state - mutable, dedicated vehicle for state changes in the proxy.
      * @param {Object|null} [options.attributes] - Optional attributes map; falls back to `policy.bound_attributes`.
      * @param {string} options.namespace - Namespace under which this proxy will be accessible in the main Glue instance.
      */
    constructor({http, name, policy, state = null, attributes = null, namespace = 'base'}) {
        /** @type {GlueHttp} */
        this.http = http
        /** @type {string} */
        this._namespace = namespace
        /** @type {string} */
        this._name = name;
        /** @type {Object} */
        this._policy = policy;
        /** @type {Object} */
        this._state = state;
        /** @type {Object} */
        this._attributes = !!attributes ? attributes : policy.bound_attributes;

        this._defineAttributeProperties()

        /**
         * @type {Object<string, Object<string, Function[]>>}
         */
        this._listeners = {
            before: {},
            after: {},
            error: {}
        }

        /** @type {Function|null} */
        this._onMessage = null
    }

    /**
     * Configure a message handler for this proxy. Overrides the global Glue client handler.
     * @param {Function|null} callback - Handler called when a GlueResponse includes messages.
     * @returns {this} The proxy instance for chaining.
     */
    onMessage(callback) {
        this._onMessage = callback;
        return this;
    }

    /**
     * Add a listener for a bound attribute.
     * @param {string} attributeName - The attribute to listen for (e.g., 'save', 'delete')
     * @param {Function} callback - The callback function
     * @param {string} [type='after'] - When to call: 'before', 'after' (default), or 'error'
     * @returns {this} The proxy instance for chaining.
     */
    addListener(attributeName, callback, type = 'after') {
        if (!this._listeners[type]) {
            throw new Error(`Invalid listener type: _${type}. Use 'before', 'after', or 'error'.`);
        }
        if (!this._listeners[type][attributeName]) {
            this._listeners[type][attributeName] = [];
        }
        this._listeners[type][attributeName].push(callback);
        return this;
    }

    /**
     * Remove a listener for a bound attribute.
     * @param {string} attributeName - The attribute name
     * @param {Function} callback - The callback to remove
     * @param {string} [type='after'] - The listener type: 'before', 'after' (default), or 'error'
     * @returns {this} The proxy instance for chaining.
     */
    removeListener(attributeName, callback, type = 'after') {
        const listeners = this._listeners[type]?.[attributeName];
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
     * Emit listeners for a given bound attribute and event type.
     * @param {string} type - Listener type: 'before', 'after', or 'error'.
     * @param {string} attributeName - The attribute name.
     * @param {Object} event - The event payload.
     */
    async emitListeners(type, attributeName, event) {

        const listeners = this._listeners?.[type]?.[attributeName] || [];
        for (const callback of listeners) {
            await callback(event);
        }
    }

    /**
     * Execute a server-side bound attribute, emitting before/after/error listeners.
     * @param {string} attributeName - The bound attribute name.
     * @param {Object|null} [eventKwargs] - Event-specific user data.
     * @returns {Promise<Object>} The server response data.
     * @private
     */
    async _processAttributeEvent(attributeName, eventKwargs = null) {
        const shortName = attributeName.split('.').pop();
        const event = {
            attribute: attributeName,
            proxy: this,
            eventKwargs: eventKwargs,
        };

        await this.emitListeners('before', shortName, event);

        this._loading = true;

        try {
            const response = await this.http.sendAttributeEventRequest({
                name: this._name,
                attribute: attributeName,
                eventKwargs: eventKwargs,
                policy: this._policy,
                state: this._state,
            });

            const responseData = response.data;

            this._handleEventResponse(attributeName, eventKwargs, responseData);
            await this._handleMessages(responseData, attributeName, eventKwargs);

            const data = responseData.result ?? {};
            event.result = data;

            await this.emitListeners('after', shortName, event);

            return data;
        } catch (err) {
            event.error = err;

            await this._handleExpiry(err, attributeName, eventKwargs);

            await this.emitListeners('error', shortName, event);
            await this._handleError(err, attributeName, eventKwargs);

            throw err;
        } finally {
            this._loading = false;
        }
    }

    async _handleError(error, attributeName, eventKwargs) {
        const handler = globalThis.Glue?._onError;
        if (!handler) {
            return;
        }

        await handler({
            error,
            proxy: this,
            attribute: attributeName,
            eventKwargs,
        });
    }

    async _handleExpiry(error, attributeName, eventKwargs) {
        if (!this._isExpiryError(error)) {
            return;
        }

        const handler = globalThis.Glue?._onExpiry || this._defaultExpiryHandler;
        await handler({
            error,
            proxy: this,
            attribute: attributeName,
            eventKwargs,
        });
    }

    _isExpiryError(error) {
        return error?.code === 'proxy_policy_expired';
    }

    _defaultExpiryHandler() {
        globalThis.alert?.('Your session has expired. Please refresh the page.');
    }

    async _handleMessages(response, attributeName, eventKwargs) {
        const messages = response?.messages || [];
        if (!Array.isArray(messages) || messages.length === 0) {
            return;
        }

        const handler = this._onMessage || globalThis.Glue?._onMessage;
        if (!handler) {
            return;
        }

        await handler({
            messages,
            response,
            proxy: this,
            attribute: attributeName,
            eventKwargs,
        });
    }

    _handleEventResponse(attributeName, eventKwargs, response) {
        if (response.policy) {
            this._policy = response.policy;
        }

        if (this._state) {
            // Mutate instance_data in place rather than replacing it.
            // This preserves Alpine's proxy wrapper so reactivity continues to work.
            if (this._state.instance_data && response.state.instance_data) {
                for (const key of Object.keys(this._state.instance_data)) {
                    if (!(key in response.state.instance_data)) {
                        delete this._state.instance_data[key];
                    }
                }
                for (const [key, value] of Object.entries(response.state.instance_data)) {
                    this._state.instance_data[key] = value;
                }
                // Update other state properties (errors, namespace, etc.) without touching instance_data
                for (const [key, value] of Object.entries(response.state)) {
                    if (key !== 'instance_data') {
                        this._state[key] = value;
                    }
                }
            } else {
                Object.assign(this._state, response.state);
            }
        } else {
            this._state = response.state;
        }
    }

    _defineAttributeProperties() {
        Object.entries(this._attributes).forEach(([attributePath, attribute]) => {
            const proxy = this
            let target = proxy;
            const attributePartsParts = attributePath.split('.')

            for (let i = 1; i < attributePartsParts.length; i++) {
                const attributePart = attributePartsParts[i]

                if (i === attributePartsParts.length - 1) {
                    target[attributePart] = async function (eventKwargs = null) {
                        return await this._processAttributeEvent(attributePath, eventKwargs);
                    };
                }
                else {
                    target[attributePart] = target
                    target = target[attributePart]
                }
            }
        });
    }
}

export default BaseGlueProxy;
