class GlueQuerySet {
    constructor(glue_unique_name) {
        this.glue_unique_name = glue_unique_name
        this.glue_encoded_unique_name = encodeUniqueName(glue_unique_name)

        // We need this value on query to build GlueModelObjects
        // this.decoded_unique_name = glue_unique_name
        // for (let key in window.glue_session_data['context'][this.glue_unique_name].fields) {
        //     this[key] = window.glue_session_data['context'][this.glue_unique_name].fields[key].value
        // }

        window.glue_keep_live.add_unique_name(this.glue_encoded_unique_name)
    }

    async all() {
        let model_object_list = []

        return await glue_ajax_request(this.glue_encoded_unique_name, 'all', {'all': true})
            .then((response) => {
                glue_dispatch_response_event(response)
                let glue_query_set = JSON.parse(response.data)

                for (let glue_field_data of glue_query_set) {
                    let glue_fields = construct_glue_fields(glue_field_data)
                    let model_object = new GlueModelObject(this.glue_unique_name, glue_fields)
                    model_object_list.push(model_object)
                }

                return model_object_list
            })
    }

    delete(id) {
        glue_ajax_request(
            this.glue_encoded_unique_name,
            'delete',
            {'id': id}
        ).then((response) => {
            glue_dispatch_response_event(response)
        })
    }

    async filter(filter_params) {
        let model_object_list = []

        return await glue_ajax_request(this.glue_encoded_unique_name, 'filter', {'filter_params': filter_params})
            .then((response) => {
                let glue_query_set = JSON.parse(response.data)
                glue_dispatch_response_event(response)

                for (let glue_field_data of glue_query_set) {
                    let glue_fields = construct_glue_fields(glue_field_data)
                    let model_object = new GlueModelObject(this.glue_unique_name, glue_fields)
                    model_object_list.push(model_object)
                }

                return model_object_list
            })
    }

    async get(id) {
        let model_object = null

        return await glue_ajax_request(this.glue_encoded_unique_name, 'get', {'id': id})
            .then((response) => {
                glue_dispatch_response_event(response)
                let response_data = JSON.parse(response.data)
                let glue_fields = construct_glue_fields(response_data[0])
                model_object = new GlueModelObject(this.glue_unique_name, glue_fields)
                return model_object
            })
    }

    async method(id, method, kwargs = {}) {
        // Todo: Should query sets be able to call methods?
        let data = {
            'id': id,
            'method': method,
            'kwargs': kwargs,
        }
        return await glue_ajax_request(
            this.glue_encoded_unique_name,
            'method',
            data
        ).then((response) => {
            glue_dispatch_response_event(response)
            return JSON.parse(response.data).method_return
        })
    }

    async null_object() {
        let data = {}

        return await glue_ajax_request(
            this.glue_encoded_unique_name,
            'null_object',
            data
        ).then((response) => {
            glue_dispatch_response_event(response)
            let glue_query_set = JSON.parse(response.data)
            let glue_fields = construct_glue_fields(glue_query_set[0])
            let model_object = new GlueModelObject(this.glue_unique_name, glue_fields)
            return model_object
        })
    }

    update(query_model_object, field = null) {
        // Todo: Update on queryset should take fields and update all the objects fields to that value.
        // Todo: Should only be able to update fields on the main table.
        // Todo: Be aware that it does not call the save method.

        let data = {}

        if (field) {
            data[field] = query_model_object[field]
        } else {
            for (let key in query_model_object.context_data.fields) {
                data[key] = query_model_object[key]
            }
        }
        glue_ajax_request(
            this.glue_encoded_unique_name,
            'update',
            data
        ).then((response) => {
            glue_dispatch_response_event(response)
        })
    }

    async to_choices(filter_params= {}) {
        return await glue_ajax_request(this.glue_encoded_unique_name, 'to_choices', {'filter_params': filter_params})
            .then((response) => {
                glue_dispatch_response_event(response)
                return JSON.parse(response.data)
            })
    }
}
