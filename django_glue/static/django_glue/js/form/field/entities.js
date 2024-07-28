
class GlueBaseFormField {
    static field_binder = null

    constructor(
        name,
        type,
        attrs = [],
        label = '',
        help_text = '',
        choices = [],
    ) {
        this.name = name
        this.type = type
        this.attrs = attrs
        this.label = label
        this.help_text = help_text
        this.choices = choices
    }

    set_attribute(name, value) {
        const existingAttrIndex = this.attrs.findIndex(attr => attr.name === name);

        if (existingAttrIndex !== -1) {
            this.attrs[existingAttrIndex].value = value;
        } else {
            this.attrs.push({ name, value });
        }
    }
}


class GlueCharField extends GlueBaseFormField {
    constructor(
        name,
        value = '',
        id = '',
        label = '',
        required = true,
        help_text = '',
        max_length = 255,
        min_length = 0
    ) {
        super(name, value, id, label, required, help_text)
        this.add_attribute('maxlength', max_length, GlueFormFieldAttrType.HTML)
        this.add_attribute('minlength', min_length, GlueFormFieldAttrType.HTML)
    }
}
