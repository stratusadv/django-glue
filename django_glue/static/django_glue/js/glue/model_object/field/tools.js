function construct_glue_field_meta(meta_data) {
    let glue_form_field = construct_glue_form_field(meta_data.glue_field)
    return new ModelObjectGlueFieldMeta(
        meta_data.type,
        meta_data.name,
        glue_form_field
    )
}


function construct_glue_field(field_data) {
    let field_meta_data = construct_glue_field_meta(field_data._meta)
    return new ModelObjectGlueField(field_data.name, field_data.value, field_meta_data)
}


function construct_glue_fields(glue_fields_data) {
    let constructed_fields = []
    for (let field_data in glue_fields_data) {
        let glue_field = construct_glue_field(glue_fields_data[field_data])
        constructed_fields.push(glue_field)
    }
    return constructed_fields
}

