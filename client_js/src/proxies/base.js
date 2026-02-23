import {sendActionRequest} from "../http";

export class BaseGlueProxy {
    constructor({proxyUniqueName, contextData, actions=null, autoFetch=false}) {
        this.uniqueName = proxyUniqueName;
        this.contextData = contextData;
        // TODO: move action data to subject_type level key in session/context_data
        this.actions = !!actions ? actions : contextData.actions;
        this.autoFetch = autoFetch

        this.defineActionsAsProperties()

        this.postInit()
    }

    setActionPayload(actionName, payload) {
        // TODO: add error handling for invalid action names
        this.actions[actionName].payload = payload;
    }

    getActionPayload(actionName) {
        return this.actions[actionName].payload
    }

    async processAction(actionName, payload = null) {
        const requestData = {
            unique_name: this.uniqueName,
            action: actionName,
            payload: payload ?? this.getActionPayload(actionName)
        };

        const response = await sendActionRequest(requestData);
        return response.data;
    }

    defineActionsAsProperties() {
        Object.keys(this.actions).forEach(actionName => {
            // Skip if subclass has already defined this method
            if (typeof this[actionName] === 'function') {
                return;
            }
            this[actionName] = (payload) => this.processAction(actionName, payload)
        });
    }

    postInit() {}
}