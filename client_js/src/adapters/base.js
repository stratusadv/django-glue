import {sendActionRequest} from "../http";

export class BaseGlueAdapter {
    constructor(uniqueName) {
        this.uniqueName = uniqueName;
        this.contextData = glueServerData.context[uniqueName];
        this.sessionData = glueServerData.session[uniqueName];
        this.actions = {};


        Object.keys(this.contextData.actions).forEach(actionName => {
            this.actions[actionName] = {payload: null, name: actionName}

            Object.defineProperty(this, actionName, {
                value: (payload) => this.actionFunctionTemplate(actionName, payload)
            });
        });

        this.postInit()
    }

    setActionPayload(actionName, payload) {
        // TODO: add error handling for invalid action names
        this.actions[actionName].payload = payload;
    }

    getActionPayload(actionName) {
        return this.actions[actionName].payload
    }

    async actionFunctionTemplate(actionName, payload = null) {
        const requestData = {
            unique_name: this.uniqueName,
            action: actionName,
            payload: this.getActionPayload(actionName)
        };

        const response = await sendActionRequest(requestData);

        if (response.ok) {
            return response.data;
        } else {
            console.error(`An error occurred when performing ${actionName} on target ${this.uniqueName}: ${response}`);
            return null;
        }
    }

    postInit() {}
}