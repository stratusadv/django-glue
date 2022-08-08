import {ajax_request} from "./ajax.js";

function get_field_data(obj) {
    let data = {}
    for (const field of obj['fields']) {
        data[field] = obj[field]
    }
    return data
}

function process_model_object(unique_name, model_object) {
    const field_data = model_object['fields']
    let data = {}

    data.update = () => {
        ajax_request(
            'PUT',
            unique_name,
            {
                form_values: get_field_data(data)
            },
        ).then((response) => {
            data['response'] = response.data
        })
    }

    data['fields'] = []

    for (let key in field_data) {
        data['fields'].push(key)
        data[key] = field_data[key].value
    }

    return data
}

function process_query_set(query_set) {
    let data = {}
    return 'Query Set'
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
