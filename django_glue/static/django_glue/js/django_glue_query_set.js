class GlueQuerySet {
    constructor(unique_name) {
        this.unique_name = unique_name
        window.glue_keep_live.add_unique_name(unique_name)
        this.context_data = {
            fields: []
        }
    }

    async all() {
        let model_object_list = []

        return await glue_ajax_request(this.unique_name, 'get', {'all': true})
            .then((response) => {
                console.log(response)
                glue_dispatch_response_event(response)
                for (let object in response.data) {
                    let model_object = new GlueModelObject(this.unique_name);
                    let simple_fields = response.data[object].simple_fields;

                    model_object.set_fields(simple_fields)
                    model_object.set_attributes_from_simple_fields(simple_fields)
                    model_object_list.push(model_object)
                }

                return model_object_list
            });
    }

    async bulk_create(query_model_object_list) {

    }

    async bulk_update(query_model_object_list) {

    }

    async create(query_model_object) {
        // Todo: Create should just take fields and not a model object.
        let data = {}

        for (let key in query_model_object.context_data.fields) {
            data[key] = query_model_object[key]
        }

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

    delete(id) {
        let data = {'id': id}
        glue_ajax_request(
            this.unique_name,
            'delete',
            data
        ).then((response) => {
            console.log(response)
            glue_dispatch_response_event(response)
        })
    }

    async filter(filter_params) {
        let model_object_list = []

        return await glue_ajax_request(this.unique_name, 'get', {'filter_params': filter_params})
            .then((response) => {
                console.log(response)
                glue_dispatch_response_event(response)
                for (let object in response.data) {
                    let model_object = new GlueModelObject(this.unique_name);
                    let simple_fields = response.data[object].simple_fields;
                    model_object.set_fields(simple_fields)
                    model_object.set_attributes_from_simple_fields(simple_fields)

                    model_object_list.push(model_object)
                }

                return model_object_list
            });
    }

    async get(id) {
        let model_object = null
        return await glue_ajax_request(this.unique_name, 'get', {'id': id})
            .then((response) => {
                model_object = new GlueModelObject(this.unique_name);
                console.log(response)
                glue_dispatch_response_event(response)
                let simple_fields = response.data.simple_fields;
                model_object.set_fields(simple_fields)
                model_object.set_attributes_from_simple_fields(simple_fields)
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
            this.unique_name,
            'method',
            data
        ).then((response) => {
            console.log(response)
            glue_dispatch_response_event(response)
            return response.data.method_return
        })
    }

    update(query_model_object, field = null) {
        // Todo: How does this work? Is this a bulk update?
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
            this.unique_name,
            'update',
            data
        ).then((response) => {
            console.log(response)
            glue_dispatch_response_event(response)
        })
    }

}