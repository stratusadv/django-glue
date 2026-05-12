export class BaseGlueProxy {
    constructor({http, proxyUniqueName, contextData, actions= null}) {
        this.http = http
        this._uniqueName = proxyUniqueName;
        this._contextData = contextData;
        // TODO: move action data to subject_type level key in session/context_data
        this._actions = !!actions ? actions : contextData.actions;

        this._listeners = {
            before: {},
            after: {},
            error: {}
        };
    }

    /**
     * Add a listener for an action.
     * @param {string} actionName - The action to listen for (e.g., 'save', 'delete')
     * @param {Function} callback - The callback function
     * @param {string} type - When to call: 'before', 'after' (default), or 'error'
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
     * @param {string} type - The listener type: 'before', 'after' (default), or 'error'
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

    clearListeners() {
        this._listeners = {};
        return this;
    }

    async emitListeners(type, actionName, event) {
        const listeners = this._listeners[type]?.[actionName] || [];
        for (const callback of listeners) {
            await callback(event);
        }
    }

    async _processAction(actionName, data = null) {
        const eventData = data instanceof FormData ? Object.fromEntries(
            Array.from(data.keys()).map(key => [
                key, data.getAll(key).length > 1 ? data.getAll(key) : data.get(key)
            ])
        ) : data;

        const event = {
            action: actionName,
            proxy: this,
            payload: eventData,
        };

        // Emit 'before' listeners
        await this.emitListeners('before', actionName, event);

        try {
            const response = await this.http.sendActionRequest({
                uniqueName: this._uniqueName,
                action: actionName,
                payload: data,
                contextData: this._contextData
            });
            event.result = response.data;

            // Emit 'after' listeners
            await this.emitListeners('after', actionName, event);

            return response.data;
        } catch (err) {
            event.error = err;

            // Emit 'error' listeners
            await this.emitListeners('error', actionName, event);

            throw err;
        }
    }
}