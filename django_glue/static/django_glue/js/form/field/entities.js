class GlueBaseFormField {

    constructor(
        name,
        {
            value = '',
            label = '',
            help_text = '',
            id = '',
            choices = [],
        } = {},
    ) {
        this.name = name
        this.value = value
        this.attrs = []
        this.label = label
        this.help_text = help_text
        this.choices = choices

        // Keeps a list of all attributes added to glue field.
        this._historic_attr_names = []
        for (const attr of this.attrs) {
            this._historic_attr_names.push(attr.name)
        }

        this.id = id === '' ? 'id_' + name : id;
    }

    get _attr_names(){
        return this.attrs.map(attr => attr.name)
    }

    get autofocus() {
        return this._get_boolean_attr('autofocus');
    }

    set autofocus(value) {
        this._set_boolean_attr('autofocus', value);
    }

    get disabled() {
        return this._get_boolean_attr('disabled');
    }

    set disabled(value) {
        this._set_boolean_attr('disabled', value);
    }

    _get_attr(name) {
        let attr = this.attrs.find(attr => attr.name === name)
        return attr ? attr.value : null;
    }

    _get_boolean_attr(name) {
        return this._get_attr(name) === true
    }

    hide_label() {
        this.label = ''
    }

    _set_boolean_attr(name, value) {
        if (value === true){
            this.set_attribute(name, value);
        } else {
            this.remove_attribute(name);
        }
    }

    remove_attribute(name) {
        this.attrs = this.attrs.filter(attr => attr.name !== name);
    }

    set_attribute(name, value) {
        const attr_index = this.attrs.findIndex(attr => attr.name === name);

        if (attr_index !== -1) {
            this.attrs[attr_index].value = value;
        } else {
            this.attrs.push({ name, value });
            this._historic_attr_names.push(name);
        }
    }

    get read_only() {
        return this._get_boolean_attr('readOnly');
    }

    set read_only(value) {
        this._set_boolean_attr('readOnly', value);
    }

    get required() {
        return this._get_boolean_attr('required');
    }

    set required(value) {
        this._set_boolean_attr('required', value);
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
            id = '',
            choices = [],
        } = {},
    ) {
        super(name, {
            value,
            label,
            help_text,
            id,
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
            id = '',
            choices = [],
        }
    ) {
        super(name, {
            value,
            label,
            help_text,
            id,
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
            id = '',
            choices = [],
            max = null,
            min = null,
        }
    ) {
        super(name, {
            value,
            label,
            help_text,
            id,
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
            id = '',
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
            id,
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
            id = '',
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
            id,
            choices,
            max,
            min,
            step,
        })
    }
}
