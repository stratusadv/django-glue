class GlueModelObject {
    constructor(unique_name) {
        this.unique_name = unique_name
        window.glue_keep_live.add_unique_name(unique_name)
        this.context_data = {
            fields: {}
        }
    }

    async create() {
        let data = this.generate_field_data()

        return await glue_ajax_request(
            this.unique_name,
            'create',
            data
        ).then((response) => {
            console.log(response)
            glue_dispatch_response_event(response)
            let model_object = new GlueModelObject(this.unique_name)

            let simple_fields = response.data.simple_fields
            model_object.set_fields(simple_fields)
            model_object.set_attributes_from_simple_fields(simple_fields)
            return model_object
        })

    }

    delete() {
        glue_ajax_request(
            this.unique_name,
            'delete'
        ).then((response) => {
            console.log(response)
            glue_dispatch_response_event(response)
        })
    }

    generate_field_data() {
        let data = {}
        for (let key in this.context_data.fields) {
            data[key] = this[key]
        }
        return data
    }

    async get(load_value = true) {
        await glue_ajax_request(
            this.unique_name,
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
            this.unique_name,
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
            this.unique_name,
            'update',
            data
        ).then((response) => {
            glue_dispatch_response_event(response)
            console.log(response)
        })
    }

}
