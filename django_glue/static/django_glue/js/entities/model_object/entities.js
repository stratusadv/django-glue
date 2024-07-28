
class GlueModelObject {
    constructor(glue_unique_name) {
        this.glue_unique_name = glue_unique_name
        this.glue_encoded_unique_name = encodeUniqueName(glue_unique_name)

        const glue_fields = construct_glue_fields(window.glue_session_data[this.glue_encoded_unique_name].fields)

        this.glue_fields_set = false

        this['fields'] = {}

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
            // console.log(response)
            glue_dispatch_response_event(response)
        }).catch((error) => {
                glue_dispatch_object_delete_error_event(error)
            }
        )
    }

    duplicate() {
        let model_object = new GlueModelObject(this.glue_unique_name)

        console.log(this.get_properties())
        model_object.set_properties(this.get_properties())
        return model_object
    }

    // Todo: Change this to load values.
    async get() {
        await glue_ajax_request(
            this.glue_encoded_unique_name,
            'get',
            {'id': this.id}
        ).then((response) => {
            glue_dispatch_response_event(response)
            // console.log(response.data)
            this._set_properties(JSON.parse(response.data))
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
            'update', {
                'fields': this.get_properties(),
                'id': this.id
            }
        ).then((response) => {
            glue_dispatch_response_event(response)
            glue_dispatch_response_event(response)
            this._set_properties(JSON.parse(response.data))

        }).catch((error) => {
                glue_dispatch_object_update_error_event(error)
            }
        )
    }

    get_properties() {
        let properties = {}

        Object.entries(this).forEach(([key, value]) => {
            properties[key] = value
        })

        return properties
    }

    _set_properties(fields) {
        // Used to set fields internally on model object.
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

    set_properties(simple_fields) {
        // Used to set initial data to the glue object model after load.
        // Send django context data and it will parse it into an object.

        if (typeof simple_fields === 'string') {
            simple_fields = parse_json_data(simple_fields)
        }

        for (let key in simple_fields) {
            if (key in this) {
                this[key] = simple_fields[key]
            }
        }
    }

    set_fields(fields) {
        // Fields are set on initialization if data is in the session.
        // Else we have to set the field data on retrieval of object

        for (let key in fields) {
           this[key] = ''
           this['fields'][key] = glue_model_field_from_field_attrs(fields[key].field_attrs)
        }

        this.glue_fields_set = true
    }
}
