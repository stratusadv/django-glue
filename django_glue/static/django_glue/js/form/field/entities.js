class GlueBaseFormField {
    static field_binder = null

    constructor(
        name,
        {
            value = '',
            label = '',
            help_text = '',
            choices = [],
        } = {},
    ) {
        this.name = name
        this.value = value
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

    is_required() {
        console.log(this.attrs.find(attr => attr.name === 'required') ?? false)
        return this.attrs.find(attr => attr.name === 'required') ?? false
    }
}


class GlueCharField extends GlueBaseFormField {
    constructor(
        name,
        {
            value = '',
            max_length = null,
            min_length = null,
            label = '',
            help_text = '',
            choices = [],
        } = {},
    ) {
        super(name, {
            value,
            label,
            help_text,
            choices,
        })
        if (max_length) {
            this.set_attribute(new GlueFormFieldAttr('maxLength', max_length))
        }

        if (min_length) {
            this.set_attribute(new GlueFormFieldAttr('minLength', min_length))
        }
    }
}


class GlueBooleanField extends GlueBaseFormField {
    constructor(
        name,
        {
            value = false,
            label = '',
            help_text = '',
            choices = [],
        }
    ) {
        super(name, {
            value,
            label,
            help_text,
            choices,
        })
        if (choices.length === 0) {
            this.choices = [[true, 'Yes'], [false, 'No']]
        }
    }
}


class GlueDateField extends GlueBaseFormField {
    constructor(
        name,
        {
            value = '',
            label = '',
            help_text = '',
            choices = [],
            max = null,
            min = null,
        }
    ) {
        super(name, {
            value,
            label,
            help_text,
            choices,
        })

        if (max) {
            this.set_attribute(new GlueFormFieldAttr('max', max))
        }

        if (min) {
            this.set_attribute(new GlueFormFieldAttr('min', min))
        }
    }
}


class GlueIntegerField extends GlueBaseFormField {
    constructor(
        name,
        {
            value = '',
            label = '',
            help_text = '',
            choices = [],
            max = null,
            min = null,
            step = 1,
        }
    ) {
        super(name, {
            value,
            label,
            help_text,
            choices,
        })

        if (max) {
            this.set_attribute(new GlueFormFieldAttr('max', max))
        }

        if (min) {
            this.set_attribute(new GlueFormFieldAttr('min', min))
        }

        if (step) {
            this.set_attribute(new GlueFormFieldAttr('step', step))
        }
    }
}


class GlueDecimalField extends GlueIntegerField {
    constructor(
        name,
        {
            value = '',
            label = '',
            help_text = '',
            choices = [],
            max = null,
            min = null,
            step = 0.1,
        }
    ) {
        super(name, {
            value,
            label,
            help_text,
            choices,
            max,
            min,
            step,
        })
    }
}

