import {ajax_request} from "./ajax.js";

function get_field_data(obj) {
    let data = {}
    for (const field of obj['glue_fields']) {
        data[field] = obj[field]
    }
    return data
}

function handle_response(response, object) {
    object['glue_response'] = response.data
    console.log(object.glue_response)
}

function process_model_object(unique_name, model_object) {
    const glue_field_data = model_object['fields']
    let data = {
        glue_fields: [],
        glue_response: null,
        glue_is_deleted: false,
        glue_create() {
            ajax_request(
                'POST',
                unique_name,
                {
                    form_values: get_field_data(this)
                },
            ).then((response) => {
                handle_response(response, this)
            })
        },
        glue_delete() {
            ajax_request(
                'DELETE',
                unique_name,
                {},
            ).then((response) => {
                handle_response(response, this)
                if (response.data.type === 'success') {
                    this.glue_is_deleted = true
                }
            })
        },
        glue_empty_data() {
            for (let key in glue_field_data) {
                this.glue_fields.push(key)
                this[key] = ''
            }
        },
        glue_load_data() {
            for (let key in glue_field_data) {
                this.glue_fields.push(key)
                this[key] = glue_field_data[key].value
            }
        },
        glue_update() {
            ajax_request(
                'PUT',
                unique_name,
                {
                    form_values: get_field_data(this)
                },
            ).then((response) => {
                handle_response(response, this)
            })
        },
        glue_view() {
            ajax_request(
                'QUERY',
                unique_name,
                {},
            ).then((response) => {
                handle_response(response, this)
                for (let key in glue_field_data) {
                    this[key] = response.data.data[key]
                }
            })
        },
    }

    data.glue_empty_data()

    return data
}

function process_query_set(unique_name, query_set) {
    const glue_field_data = []
    let data = {
        glue_fields: [],
        glue_response: null,
        glue_create() {
            ajax_request(
                'POST',
                unique_name,
                {
                    form_values: get_field_data(this),
                },
            ).then((response) => {
                handle_response(response, this)
            })
        },
        glue_delete(id) {
            ajax_request(
                'DELETE',
                unique_name,
                {
                    id: id,
                },
            ).then((response) => {
                handle_response(response, this)
            })
        },
        glue_update(id) {
            ajax_request(
                'PUT',
                unique_name,
                {
                    id: id,
                    form_values: get_field_data(this),
                },
            ).then((response) => {
                handle_response(response, this)
            })
        },
        glue_view(id=0) {
            ajax_request(
                'QUERY',
                unique_name,
                {
                    id: id,
                },
            ).then((response) => {
                handle_response(response, this)
            })
        }
    }

    for (let key in glue_field_data) {
        data['fields'].push(key)
        data[key] = glue_field_data[key].value
    }

    return data
}


document.addEventListener('alpine:init', () => {
    let glue_data = {}

    for (let key in DJANGO_GLUE_DATA) {
        let data

        if (DJANGO_GLUE_DATA[key].connection === 'model_object') {
            data = process_model_object(key, DJANGO_GLUE_DATA[key])
        }

        if (DJANGO_GLUE_DATA[key].connection === 'query_set') {
            data = process_query_set(key, DJANGO_GLUE_DATA[key])
        }

        glue_data[key] = data

        Alpine.data(key, () => (data))
    }

    Alpine.data('glue', () => (glue_data))
})
