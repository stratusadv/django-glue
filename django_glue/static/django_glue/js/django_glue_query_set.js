class GlueQuerySet {
    constructor(unique_name) {
        this.unique_name = unique_name
        this.context_data = null
        if (unique_name in DJANGO_GLUE_CONTEXT_DATA) {
            this.context_data = DJANGO_GLUE_CONTEXT_DATA[unique_name]
            if (this.context_data.connection !== 'query_set') {
                console.error('"' + unique_name + '" is not a query set')
            }
        } else {
            console.error('"' + unique_name + '" is and invalid glue unique name.')
        }
    }

     async get(id) {
        let model_object_list = []
        let model_object = null
        return await glue_ajax_request(this.unique_name, 'get', {'id': id})
            .then((response) => {
               model_object = new GlueModelObject(this.unique_name);
                console.log(response)
                let simple_fields = response.data.simple_fields;
                for (let key in simple_fields) {
                    model_object[key] = simple_fields[key];
                }
                model_object_list.push(model_object)
                return model_object_list
            });
    }

    async all(){
        let model_object_list = []
        let model_object = null

        return await glue_ajax_request(this.unique_name, 'get', {'all': true})
            .then((response) => {
                console.log(response)
                for (let object in response.data){
                    model_object = new GlueModelObject(this.unique_name);

                    let simple_fields = response.data[object].simple_fields;
                    for (let key in simple_fields) {
                        model_object[key] = simple_fields[key];
                    }
                    model_object_list.push(model_object)
                }

                return model_object_list
            });
    }

    update(query_model_object, field = null) {
        let data = {}

        if (field) {
            data[field] = query_model_object[field]
        }
        else {
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
        })
    }

    async filter(filter_params){
        let model_object_list = []
        let model_object = null

        return await glue_ajax_request(this.unique_name, 'get', {'filter_params': filter_params})
            .then((response) => {
                console.log(response)
                for (let object in response.data){
                    model_object = new GlueModelObject(this.unique_name);

                    let simple_fields = response.data[object].simple_fields;
                    for (let key in simple_fields) {
                        model_object[key] = simple_fields[key];
                    }
                    model_object_list.push(model_object)
                }

                return model_object_list
            });
    }

    create(query_model_object) {
        let data = {}

        for (let key in query_model_object.context_data.fields) {
            data[key] = query_model_object[key]
        }

        glue_ajax_request(
            this.unique_name,
            'create',
            data
        ).then((response) => {
            console.log(response)
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
        })
    }

    method() {

    }

}