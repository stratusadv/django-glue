function django_glue_init() {
    let data = {}

    for (let key in DJANGO_GLUE_DATA) {
        if(DJANGO_GLUE_DATA[key].connection === 'model_object') {
            data[key] = process_model_object(DJANGO_GLUE_DATA[key])
        }
        if(DJANGO_GLUE_DATA[key].connection === 'query_set') {
            data[key] = process_query_set(DJANGO_GLUE_DATA[key])
        }
    }

    return data

}

function process_model_object(model_object) {
    const fields = model_object['fields']
    let data = {
        tacos: 'Yummy',
        create() {
            alert('Creating New'+model_object)
        }
    }

    for (let key in fields) {
        data[key] = fields[key].value
    }

    return data
}

function process_query_set(query_set) {
    return 'Query Set'
}


document.addEventListener('alpine:init', () => {
    Alpine.data('glue', () => (django_glue_init()))
})
