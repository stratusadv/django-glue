function construct_glue_form_field(glue_field_data) {
    let options = Object.assign({
        label: glue_field_data.label,
        help_text: glue_field_data.help_text,
        choices: glue_field_data.choices,
        id: glue_field_data.id,
    });

    let glue_form_field = new GlueBaseFormField(glue_field_data.name, options)

    let field_attrs = construct_form_field_attrs(glue_field_data.attrs)
    let setters = ['required', 'hidden', 'read_only', 'autofocus', 'disabled', 'prevent_submit']

    for (let field_attr of field_attrs) {
        if (setters.includes(field_attr.name)) {
            glue_form_field[field_attr.name] = field_attr.value
        } else {
            glue_form_field.set_attribute(field_attr.name, field_attr.value)
        }
    }

    return glue_form_field
}
