class GlueModelObject {
    constructor(glue_unique_name, fields = []) {
        this['_meta'] = {
            'glue_unique_name': glue_unique_name,
            'glue_encoded_unique_name': encodeUniqueName(glue_unique_name),
            'glue_fields_set': false
        }

        if (fields.length === 0) {
            let glue_session_fields = construct_glue_fields(window.glue_session_data[this['_meta']['glue_encoded_unique_name']].fields)
            for (let field of glue_session_fields) {
                fields.push(field)
            }
        }

        this._set_properties(fields)
        this.set_fields(fields)

        if (this['_meta']['glue_encoded_unique_name'] in window.glue_session_data) {
        }

        window.glue_keep_live.add_unique_name(this['_meta']['glue_encoded_unique_name'])
    }

    delete() {
        glue_ajax_request(
            this['_meta']['glue_encoded_unique_name'],
            'delete',
            {'id': this.id}
        ).then((response) => {
            glue_dispatch_response_event(response)
        }).catch((error) => {
                glue_dispatch_object_delete_error_event(error)
            }
        )
    }

    duplicate() {
        let model_object = new GlueModelObject(this.glue_unique_name)
        model_object.set_properties(this.get_properties())
        return model_object
    }

    async get() {
        await glue_ajax_request(
            this['_meta']['glue_encoded_unique_name'],
            'get',
            {'id': this.id}
        ).then((response) => {
            glue_dispatch_response_event(response)
            let glue_fields = construct_glue_fields(JSON.parse(response.data))
            this._set_properties(glue_fields)
        }).catch((error) => {
                glue_dispatch_object_get_error_event(error)
            }
        )
    }

    get glue_fields() {
        return new Proxy({}, {
            get: (target, prop) =>
            {
                if (!this._meta || !this._meta[prop] || !this._meta[prop]._meta) {
                  return undefined;
                }
                return this._meta[prop]._meta.glue_field;
            }
        });
    }

    async method(method, kwargs = {}) {
        let data = {
            'id': this.id,
            'method': method,
            'kwargs': kwargs,
        }

        return await glue_ajax_request(
            this['_meta']['glue_encoded_unique_name'],
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
            this['_meta']['glue_encoded_unique_name'],
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
            if (!key.startsWith('_')) {
                properties[key] = value
            }
        })

        return properties
    }

    _set_properties(fields) {
        // Array of glue model field objects
        // Used to set fields internally on model object.
        if (!this['_meta']['glue_fields_set']) {
            this.set_fields(fields)
        }

        for (let field of fields) {
            this[field.name] = field.value
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
        // Array of glue model field objects
        for (let field of fields) {
            this['_meta'][field.name] = field
        }

        this['_meta']['glue_fields_set'] = true
    }
}
