class GlueModelObject {
    constructor(unique_name, load_values = true) {
        this.unique_name = unique_name
        this.context_data = null

        console.log(DJANGO_GLUE_CONTEXT_DATA)

        if (unique_name in DJANGO_GLUE_CONTEXT_DATA) {
            this.context_data = DJANGO_GLUE_CONTEXT_DATA[unique_name]

            if (this.context_data.connection === 'model_object' || this.context_data.connection === 'query_set') {
                this.load_fields(load_values)
            } else {
                console.error('"' + unique_name + '" is not a model object')
            }

        } else {
            console.error('"' + unique_name + '" is and invalid glue unique name.')
        }

    }

    load_fields(load_values = true) {
        if (load_values) {
            this.load_values()
        } else {
            for (let key in this.context_data.fields) {
                this[key] = ''
            }
        }
    }

    load_values() {
        for (let key in this.context_data.fields) {
            this[key] = this.context_data.fields[key].value
        }
    }

    get() {
        glue_ajax_request(
            this.unique_name,
            'get'
        ).then((response) => {
            console.log(response)
            let simple_fields = response.data.simple_fields
            for (let key in simple_fields) {
                this[key] = simple_fields[key]
            }
        })
    }

    update(field = null) {
        let data = {}

        if (field) {
            data[field] = this[field]
        }
        else {
            for (let key in this.context_data.fields) {
                data[key] = this[key]
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

    create() {
        let data = {}

        for (let key in this.context_data.fields) {
            data[key] = this[key]
        }

        glue_ajax_request(
            this.unique_name,
            'create',
            data
        ).then((response) => {
            console.log(response)
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

    method() {

    }

}
