class GlueModelObject {

    constructor(glue_unique_name) {
        // We are encoding the unique name twice when
        this.glue_unique_name = glue_unique_name
        this.glue_encoded_unique_name = encodeUniqueName(glue_unique_name)

        // this['form_fields'] = {}
        for (let key in window.glue_session_data[this.glue_encoded_unique_name].fields) {
           this[key] = ''
           // this['form_fields'][key] = window.glue_session_data['context'][this.glue_encoded_unique_name].fields[key]
        }
        window.glue_keep_live.add_unique_name(this.glue_encoded_unique_name)
    }

    delete() {
        glue_ajax_request(
            this.glue_encoded_unique_name,
            'delete'
        ).then((response) => {
            console.log(response)
            glue_dispatch_response_event(response)
        }).catch((error) => {
                glue_dispatch_object_delete_error_event(error)
            }
        )
    }

    async get() {
        await glue_ajax_request(
            this.glue_encoded_unique_name,
            'get'
        ).then((response) => {
            glue_dispatch_response_event(response)

            // Set the properties on the object
            Object.entries(response.data).forEach(([key, field]) => {
                this[key] = field.value
            });

        }).catch((error) => {
                glue_dispatch_object_get_error_event(error)
            }
        )
    }

    async method(method, kwargs = {}) {
        let data = {
            'method': method,
            'kwargs': kwargs,
        }

        return await glue_ajax_request(
            this.glue_encoded_unique_name,
            'method',
            data
        ).then((response) => {
            glue_dispatch_response_event(response)
            return response.data.method_return
        }).catch((error) => {
                glue_dispatch_object_method_error_event(error)
            }
        )
    }

    async update(field = null) {
        await glue_ajax_request(
            this.glue_encoded_unique_name,
            'update',
            {'fields': this.get_properties()}
        ).then((response) => {
            glue_dispatch_response_event(response)
            console.log(response)
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

    set_properties(properties) {
        // Only sets properties that are already initialized on the glue object model.
        for (let key in properties) {
            if (key in this) {
                this[key] = properties[key]
            }
        }
    }

}
