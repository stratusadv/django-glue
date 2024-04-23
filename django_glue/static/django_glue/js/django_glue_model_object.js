class GlueModelObject {

    constructor(glue_unique_name) {
        // We are encoding the unique name twice when
        this.glue_unique_name = glue_unique_name
        console.log("Pathname:", window.location.pathname);

        this.glue_encoded_unique_name = encodeUniqueName(glue_unique_name)
        console.log(glue_unique_name)
        console.log(encodeUniqueName(glue_unique_name))
        this.glue_fields_set = false

        // this['html_attr'] = {}
        if (this.glue_encoded_unique_name in window.glue_session_data) {
            this.set_fields(window.glue_session_data[this.glue_encoded_unique_name].fields)
        }

        window.glue_keep_live.add_unique_name(this.glue_encoded_unique_name)
    }

    delete() {
        glue_ajax_request(
            this.glue_encoded_unique_name,
            'delete',
            {'id': this.id}
        ).then((response) => {
            console.log(response)
            glue_dispatch_response_event(response)
        }).catch((error) => {
                glue_dispatch_object_delete_error_event(error)
            }
        )
    }

    // Todo: Change this to load values.
    async get() {
        await glue_ajax_request(
            this.glue_encoded_unique_name,
            'get',
            {
                'id': this.id,
            }
        ).then((response) => {
            glue_dispatch_response_event(response)
            this.set_properties(JSON.parse(response.data))
        }).catch((error) => {
                glue_dispatch_object_get_error_event(error)
            }
        )
    }

    async method(method, kwargs = {}) {
        let data = {
            'id': this.id,
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
        }).catch((error) => {
                glue_dispatch_object_method_error_event(error)
            }
        )
    }

    async update(field = null) {
        await glue_ajax_request(
            this.glue_encoded_unique_name,
            'update',
            {
                'fields': this.get_properties(),
                'id': this.id
            }
        ).then((response) => {
            glue_dispatch_response_event(response)
            console.log(response)
            glue_dispatch_response_event(response)
            this.set_properties(JSON.parse(response.data))

        }).catch((error) => {
                glue_dispatch_object_update_error_event(error)
            }
        )
    }

    get_properties() {
        let properties = {}
        Object.entries(this).forEach(([key, value]) => {
            properties[key] = value
        });
        return properties
    }

    set_properties(fields) {
        // Only sets properties that are already initialized on the glue object model.
        if (!this.glue_fields_set) {
            this.set_fields(fields)
        }
        let simple_fields = simplify_model_fields(fields)
        for (let key in simple_fields) {
            if (key in this) {
                this[key] = simple_fields[key]
            }
        }
    }

    set_fields(fields){
        for (let key in fields) {
           this[key] = ''
           // this['form_fields'][key] = window.glue_session_data['context'][this.glue_encoded_unique_name].fields[key]
        }
        this.glue_fields_set = true

    }

}
