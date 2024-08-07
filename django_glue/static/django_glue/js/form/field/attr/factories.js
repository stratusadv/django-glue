function construct_form_field_attrs(attr_data) {
    let attrs = []
    for (let attr of attr_data) {
        attrs.push(new GlueFormFieldAttr(attr.name, attr.value))
    }
    return attrs
}