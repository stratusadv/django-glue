class GlueModelObject {
    constructor(unique_name) {
        this.glue_unique_name = unique_name

        console.log(window.glue_session_data)

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

    async get(load_value = true) {
        await glue_ajax_request(
            this.glue_unique_name,
            'get'
        ).then((response) => {
            console.log(response)
            glue_dispatch_response_event(response)

            let simple_fields = response.data.simple_fields
            this.set_fields(simple_fields)
            this.set_attributes_from_simple_fields(simple_fields, load_value)
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

    set_fields(simple_fields) {
        for (let key in simple_fields) {
            this.context_data.fields[key] = simple_fields[key]
        }
    }

    set_attributes_from_simple_fields(simple_fields, load_value = true) {
        for (let key in simple_fields) {
            if (load_value) {
                this[key] = simple_fields[key]
            } else {
                this[key] = null
            }
        }
    }

    async update(field = null) {
        let data = {}

        if (field) {
            data[field] = this[field]
        } else {
            data = this.generate_field_data()
        }

        await glue_ajax_request(
            this.glue_unique_name,
            'update',
            data
        ).then((response) => {
            glue_dispatch_response_event(response)
            console.log(response)
        })
    }

    get_properties() {
        let properties = {}
        Object.entries(this).forEach(([key, value]) => {
            if (!key.startsWith('glue')) {
                data[key] = value
            }
        });
        console.log(properties)
        return properties
    }

    set_properties(properties) {
        for (let key in properties) {
            this[key] = properties[key]
        }
    }

}
