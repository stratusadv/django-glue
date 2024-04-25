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
                for (let object in glue_query_set) {
                    let model_object = new GlueModelObject(this.glue_unique_name);
                    model_object.set_properties(glue_query_set[object])
                    model_object_list.push(model_object)
                }
                return model_object_list
            });
    }

    async bulk_create(query_model_object_list) {

    }

    async bulk_update(query_model_object_list) {

    }

    delete(id) {
        glue_ajax_request(
            this.glue_encoded_unique_name,
            'delete',
            {'id': id}
        ).then((response) => {
            console.log(response)
            glue_dispatch_response_event(response)
        })
    }

    async filter(filter_params) {
        let model_object_list = []

        return await glue_ajax_request(this.glue_encoded_unique_name, 'filter', {'filter_params': filter_params})
            .then((response) => {
                console.log(response)
                let glue_query_set = JSON.parse(response.data)
                glue_dispatch_response_event(response)
                for (let object in glue_query_set) {
                    let model_object = new GlueModelObject(this.glue_unique_name)
                    model_object.set_properties(glue_query_set[object])
                    model_object_list.push(model_object)
                }

                return model_object_list
            });
    }

    async get(id) {
        let model_object = null
        return await glue_ajax_request(this.glue_encoded_unique_name, 'get', {'id': id})
            .then((response) => {
                glue_dispatch_response_event(response)
                model_object = new GlueModelObject(this.glue_unique_name);
                let glue_query_set = JSON.parse(response.data)
                model_object.set_properties(glue_query_set[0])
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
            this.glue_encoded_unique_name,
            'method',
            data
        ).then((response) => {
            console.log(response)
            glue_dispatch_response_event(response)
            return JSON.parse(response.data).method_return
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
            console.log(response)
            glue_dispatch_response_event(response)
        })
    }

}