
class GlueBaseFormField {
    static field_binder = null

    constructor(
        name,
        id = '',
        label = '',
        required = true,
        help_text = '',
        attrs = []
    ) {
        this.name = name
        this.id = id
        this.label = label
        this.required = required
        this.help_text = help_text
    }

    set_attribute(name, value) {
        this[name] = value
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
