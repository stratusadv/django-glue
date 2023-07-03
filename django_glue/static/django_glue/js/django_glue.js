async function glue_model_object(unique_name){
    let new_model_object = new GlueModelObject(unique_name)
    await new_model_object.get()
    return new_model_object
}