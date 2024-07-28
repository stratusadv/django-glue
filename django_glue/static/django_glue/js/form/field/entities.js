


class GlueBaseFormField {
    static field_binder = null

    constructor(
        name,
        {
            label = '',
            help_text = '',
            choices = [],
        } = {},
    ) {
        this.name = name
        this.value = ''
        this.attrs = []
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
        value = false,
        max_length = null,
        min_length = null,
        label = '',
        help_text = '',
        choices = [],
    ) {
        super(name, label, help_text, choices)
        if (Number.isInteger(max_length)) {
            this.set_attribute(new GlueFormFieldAttr('maxLength', max_length))
        }

        if (Number.isInteger(min_length)) {
            this.set_attribute(new GlueFormFieldAttr('minLength', min_length))
        }
    }
}


class GlueBooleanField extends GlueBaseFormField {
    constructor(
        name,
        attrs = [],
        label = '',
        help_text = '',
        choices = [],
    ) {
        super(name, attrs, label, help_text, choices)
        if (choices.length === 0) {
            this.choices = [[true, 'Yes'], [false, 'No']]
        }
    }
}


class GlueDateField extends GlueBaseFormField {
    constructor(
        name,
        attrs = [],
        label = '',
        help_text = '',
        choices = [],
    ) {
        super(name, attrs, label, help_text, choices)
        if (choices.length === 0) {
            this.choices = [[true, 'Yes'], [false, 'No']]
        }
    }
}
