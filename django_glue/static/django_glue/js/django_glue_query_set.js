class GlueQuerySet {
    constructor(unique_name) {
        this.unique_name = unique_name
        this.context_data = null
        if (unique_name in DJANGO_GLUE_CONTEXT_DATA){
            this.context_data = DJANGO_GLUE_CONTEXT_DATA[unique_name]
            if (this.context_data.connection !== 'query_set'){
                console.error('"' + unique_name + '" is not a query set')
            }
        }else {
            console.error('"' + unique_name + '" is and invalid glue unique name.')
        }
    }

    get(id) {
      let model_object = null;
      return glue_ajax_request(this.unique_name, 'get', {'id': id})
        .then(response => {
          model_object = new GlueModelObject(this.unique_name);

          let simple_fields = response.data.simple_fields;
          for (let key in simple_fields) {
            model_object[key] = simple_fields[key];
          }

          return model_object;
        });
    }

    update(){

    }

    create(){

    }

    delete(){

    }

    methode(){

    }

}