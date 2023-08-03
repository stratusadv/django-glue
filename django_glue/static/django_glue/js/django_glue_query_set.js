class GlueQuerySet {
    constructor(unique_name) {
        this.glue_unique_name = unique_name

        for (let key in window.glue_session_data['context'][unique_name].fields) {
            this[key] = window.glue_session_data['context'][unique_name].fields[key].value
        }

        window.glue_keep_live.add_unique_name(unique_name)
    }

    async all() {
        let model_object_list = []

        return await glue_ajax_request(this.glue_unique_name, 'get', {'all': true})
            .then((response) => {
                console.log(response)
                glue_dispatch_response_event(response)
                for (let object in response.data) {
                    let model_object = new GlueModelObject(this.glue_unique_name);
                    model_object.set_properties(response.data[object].simple_fields)
                    model_object_list.push(model_object)
                }

                return model_object_list
            });
    }

    async bulk_create(query_model_object_list) {

    }

    async bulk_update(query_model_object_list) {

    }

    async create(model_object) {
        // Todo: Should this be a model object or should it just be data?
        return await glue_ajax_request(
            this.glue_unique_name,
            'create',
            model_object.get_properties()
        ).then((response) => {
            console.log(response)
            glue_dispatch_response_event(response)
            return model_object
        })
    }

    delete(id) {
        glue_ajax_request(
            this.glue_unique_name,
            'delete',
            {'id': id}
        ).then((response) => {
            console.log(response)
            glue_dispatch_response_event(response)
        })
    }

    async filter(filter_params) {
        let model_object_list = []

        return await glue_ajax_request(this.glue_unique_name, 'get', {'filter_params': filter_params})
            .then((response) => {
                console.log(response)
                glue_dispatch_response_event(response)
                for (let object in response.data) {
                    let model_object = new GlueModelObject(this.glue_unique_name);
                    model_object.set_properties(response.data[object].simple_fields)
                    model_object_list.push(model_object)
                }

                return model_object_list
            });
    }

    async get(id) {
        let model_object = null
        return await glue_ajax_request(this.glue_unique_name, 'get', {'id': id})
            .then((response) => {
                console.log(response)
                glue_dispatch_response_event(response)
                model_object = new GlueModelObject(this.glue_unique_name);
                model_object.set_properties(response.data.simple_fields)
                return model_object
            });
    }

    async method(id, method, kwargs = {}) {
        // Todo: Should query sets be able to call methods?
        let data = {
            'id': id,
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
            this.glue_unique_name,
            'update',
            data
        ).then((response) => {
            console.log(response)
            glue_dispatch_response_event(response)
        })
    }

}