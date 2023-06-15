class GlueQuerySet {
    constructor(unique_name, load_values= true) {
        this.unique_name = unique_name
        this.context_data = null

        if (unique_name in DJANGO_GLUE_CONTEXT_DATA){
            this.context_data = DJANGO_GLUE_CONTEXT_DATA[unique_name]

            if (this.context_data.connection === 'query_set'){

            }

        }
    }
}