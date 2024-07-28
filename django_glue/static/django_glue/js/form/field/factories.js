function construct_glue_form_field(glue_field_data) {
    let glue_form_field = new GlueBaseFormField(
        glue_field_data.name,
        {
            label: glue_field_data.label,
            help_text: glue_field_data.help_text,
            choices: glue_field_data.choices,
        }
    )

    let field_attrs = construct_form_field_attrs(glue_field_data.attrs)
    for (let field_attr of field_attrs) {
        glue_form_field.set_attribute(field_attr.name, field_attr.value)
    }

    return glue_form_field
}
