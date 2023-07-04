class GlueModelObject {
    constructor(unique_name) {
        this.unique_name = unique_name
        this.context_data = {}
    }

    async get(load_value = true) {
        this.context_data.fields = []
        await glue_ajax_request(
            this.unique_name,
            'get'
        ).then((response) => {
            console.log(response)
            let simple_fields = response.data.simple_fields
            for (let key in simple_fields) {
                if (load_value) {
                    this[key] = simple_fields[key]
                } else {
                    this[key] = null
                }
                this.context_data.fields.push(key)
            }
        })
    }

    async update(field = null) {
        let data = {}

        if (field) {
            data[field] = this[field]
        } else {
            for (let key in this.context_data.fields) {
                data[key] = this[key]
            }
        }

        await glue_ajax_request(
            this.unique_name,
            'update',
            data
        ).then((response) => {
            console.log(response)
        })
    }

    async create() {
        let data = {}

        for (let key in this.context_data.fields) {
            data[key] = this[key]
        }

        return await glue_ajax_request(
            this.unique_name,
            'create',
            data
        ).then((response) => {
            console.log(response)
            let model_object = new GlueModelObject(this.unique_name)

            let simple_fields = response.data.simple_fields
            for (let key in simple_fields) {
                model_object[key] = simple_fields[key]
            }
            return model_object
        })

    }

    delete() {
        glue_ajax_request(
            this.unique_name,
            'delete'
        ).then((response) => {
            console.log(response)
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
            return response.data.method_return
        })
    }

}
