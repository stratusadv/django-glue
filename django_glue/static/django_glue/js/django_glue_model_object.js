class GlueModelObject {
    constructor(unique_name) {
        this.unique_name = unique_name

        if(unique_name in DJANGO_GLUE_CONTEXT_DATA) {
            if (DJANGO_GLUE_CONTEXT_DATA[unique_name].connection === 'model_object') {

            } else {
                console.error('"' + unique_name + '" is not a model object')
            }
            this.first_name = 'Mr Testy'
            this.last_name = 'Pants'
        } else {
            console.error('"' + unique_name + '" is and invalid glue unique name.')
        }

    }
}
