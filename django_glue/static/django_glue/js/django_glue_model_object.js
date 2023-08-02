class GlueModelObject {
    constructor(unique_name) {
        this.glue_unique_name = unique_name

        for (let key in window.glue_session_data['context'][unique_name].fields) {
            this[key] = null
        }

        window.glue_keep_live.add_unique_name(unique_name)
    }

    async create() {
        return await glue_ajax_request(
            this.glue_unique_name,
            'create',
            this.get_properties()
        ).then((response) => {
            console.log(response)
            glue_dispatch_response_event(response)
            return this
        })
    }

    delete() {
        glue_ajax_request(
            this.glue_unique_name,
            'delete'
        ).then((response) => {
            console.log(response)
            glue_dispatch_response_event(response)
        })
    }

    async get() {
        await glue_ajax_request(
            this.glue_unique_name,
            'get'
        ).then((response) => {
            console.log(response)
            glue_dispatch_response_event(response)
            this.set_properties(response.data.simple_fields)
        })
    }

    async method(method, kwargs = {}) {
        let data = {
            'method': method,
            'kwargs': kwargs,
        }

        return await glue_ajax_request(
            this.glue_unique_name,
            'method',
            data
        ).then((response) => {
            console.log(response)
            glue_dispatch_response_event(response)
            return response.data.method_return
        })
    }

    async update(field = null) {
        await glue_ajax_request(
            this.glue_unique_name,
            'update',
            this.get_properties()
        ).then((response) => {
            glue_dispatch_response_event(response)
            console.log(response)
        })
    }

    get_properties() {
        let properties = {}
        Object.entries(this).forEach(([key, value]) => {
            if (!key.startsWith('glue')) {
                properties[key] = value
            }
        });
        return properties
    }

    set_properties(properties) {
        for (let key in properties) {
            this[key] = properties[key]
        }
    }

}
