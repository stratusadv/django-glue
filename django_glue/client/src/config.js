import {sendActionRequest} from "./http-client";

export class ModelGlue {
    constructor(uniqueName) {
        this.glue = glueServerData.session[uniqueName]
        this.loaded = false
        this.loading = false
        this.values = {}
        this.actionPayloads = {}

        Object.keys(glueServerData.context[uniqueName].actions).forEach(actionName => {
            Object.defineProperty(this, actionName, {
                value: async function (payload = null) {
                    const requestData = {
                        unique_name: uniqueName,
                        action: actionName,
                        payload: actionName in this.actionPayloads ? this.actionPayloads[actionName] : null
                    }

                    const response = await sendActionRequest(requestData)

                    if (response.ok) {
                        return response.data
                    }
                    else {
                        console.error(`An error occurred when performing ${name} on target ${uniqueName}: ${response}`)
                        return null
                    }
                }
            })
        })

        Object.keys(glueServerData.context[uniqueName].fields).forEach(fieldName => {
            Object.defineProperty(this, fieldName, {
                get: function() {
                    // This getter should return the current value
                    if (!this.loaded) {
                        // Trigger loading if needed
                        if (!this.loading) {
                            this.loading = true;
                            this.get().then(data => {
                                // Update the values when loaded
                                this.values = data;
                            }).finally(() => {
                                this.loading = false;
                                this.loaded = true;
                            });
                        }
                    }

                    // Return the current value
                    return this.values?.[fieldName];
                },
                set: function(value) {
                    // Handle setting values for two-way binding
                    if (!this.values) {
                        this.values = {};
                    }
                    this.values[fieldName] = value;

                    this.actionPayloads['save'] = this.values
                }
            })
        })
    }
}