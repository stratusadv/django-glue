import {sendActionRequest} from "../http";

export class BaseGlueProxy {
    constructor({proxyUniqueName, contextData, actions= null}) {
        this.uniqueName = proxyUniqueName;
        this.contextData = contextData;
        // TODO: move action data to subject_type level key in session/context_data
        this.actions = !!actions ? actions : contextData.actions;

        this.listeners = {
            before: {},
            after: {},
            error: {}
        };
    }

    setActionPayload(actionName, payload) {
        // TODO: add error handling for invalid action names
        this.actions[actionName].payload = payload;
    }

    getActionPayload(actionName) {
        return this.actions[actionName].payload
    }

    /**
     * Add a listener for an action.
     * @param {string} actionName - The action to listen for (e.g., 'save', 'delete')
     * @param {Function} callback - The callback function
     * @param {string} type - When to call: 'before', 'after' (default), or 'error'
     */
    addListener(actionName, callback, type = 'after') {
        if (!this.listeners[type]) {
            throw new Error(`Invalid listener type: ${type}. Use 'before', 'after', or 'error'.`);
        }
        if (!this.listeners[type][actionName]) {
            this.listeners[type][actionName] = [];
        }
        this.listeners[type][actionName].push(callback);
        return this;
    }

    /**
     * Remove a listener for an action.
     * @param {string} actionName - The action name
     * @param {Function} callback - The callback to remove
     * @param {string} type - The listener type: 'before', 'after' (default), or 'error'
     */
    removeListener(actionName, callback, type = 'after') {
        const listeners = this.listeners[type]?.[actionName];
        if (listeners) {
            const index = listeners.indexOf(callback);
            if (index > -1) {
                listeners.splice(index, 1);
            }
        }
        return this;
    }

    async emitListeners(type, actionName, event) {
        const listeners = this.listeners[type]?.[actionName] || [];
        for (const callback of listeners) {
            await callback(event);
        }
    }

    async processAction(actionName, payload = null) {
        payload = payload ?? this.getActionPayload(actionName)

        const event = {
            action: actionName,
            proxy: this,
            payload,
        };

        // Emit 'before' listeners
        await this.emitListeners('before', actionName, event);

        try {
            const response = await sendActionRequest({
                uniqueName: this.uniqueName,
                action: actionName,
                payload: payload ?? this.getActionPayload(actionName),
                contextData: this.contextData
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