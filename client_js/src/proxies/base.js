import {sendActionRequest} from "../http";

export class BaseGlueProxy {
    constructor(proxyRegistryData, contextData) {
        this.uniqueName = proxyRegistryData.unique_name;
        this.contextData = contextData;
        this.actions = contextData.actions;

        this.#defineActionsAsProperties()

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

        if (response.ok) {
            return response.data;
        } else {
            console.error(`An error occurred when performing ${actionName} on target ${this.uniqueName}: ${response}`);
            return null;
        }
    }

    #defineActionsAsProperties() {
        Object.keys(this.actions).forEach(actionName => this.defineActionAsProperty(actionName));
    }

    defineActionAsProperty(actionName) {
        Object.defineProperty(this, actionName, {
            value: (payload) => this.processAction(actionName, payload)
        });
    }

    postInit() {}
}