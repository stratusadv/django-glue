class GlueBaseFormField {

    constructor(
        name,
        {
            value = '',
            label = '',
            help_text = '',
            id = '',
            choices = [],
            required = false,
            disabled = false,
            readonly = false,
            hidden = false,
            autofocus = false,
            prevent_submit = false
        } = {},
    ) {
        this.name = name
        this.value = value
        this.attrs = []
        this.label = label
        this.help_text = help_text
        this.choices = choices
        this.required = required
        this.hidden = hidden
        this.read_only = readonly
        this.autofocus = autofocus
        this.disabled = disabled
        this.prevent_submit = prevent_submit

        this._hide_label = false

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
        this._hide_label = true
    }

    show_label() {
        this._hide_label = false
    }

    get hidden() {
        return this._get_boolean_attr('hidden');
    }

    set hidden(value) {
        this._set_boolean_attr('hidden', value);
        if (value === true) {
            this.hide_label()
        } else {
            this.show_label()
        }

    }

    get prevent_submit(){
        return Boolean(this._get_attr('name'))
    }

    set prevent_submit(value){
        if (value){
            this.remove_attribute('name')
        } else {
            this.set_attribute('name', this.name)
        }
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
            this.attrs.push(new GlueFormFieldAttr(name, value));
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
            required = false,
            disabled = false,
            readonly = false,
            hidden = false,
            autofocus = false,
            prevent_submit = false,
        } = {},
    ) {
        super(name, {
            value,
            label,
            help_text,
            id,
            choices,
            required,
            disabled,
            readonly,
            hidden,
            autofocus,
            prevent_submit
        })
        if (max_length) {
            this.set_attribute('maxLength', max_length)
        }

        if (min_length) {
            this.set_attribute('minLength', min_length)
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
            required = false,
            disabled = false,
            readonly = false,
            hidden = false,
            autofocus = false,
            prevent_submit = false,
        }
    ) {
        super(name, {
            value,
            label,
            help_text,
            id,
            choices,
            required,
            disabled,
            readonly,
            hidden,
            autofocus,
            prevent_submit
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
            required = false,
            disabled = false,
            readonly = false,
            hidden = false,
            autofocus = false,
            prevent_submit = false,
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
            required,
            disabled,
            readonly,
            hidden,
            autofocus,
            prevent_submit
        })

        if (max) {
            this.set_attribute('max', max)
        }

        if (min) {
            this.set_attribute('min', min)
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
            required = false,
            disabled = false,
            readonly = false,
            hidden = false,
            autofocus = false,
            prevent_submit = false,
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
            required,
            disabled,
            readonly,
            hidden,
            autofocus,
            prevent_submit
        })

        if (max) {
            this.set_attribute('max', max)
        }

        if (min) {
            this.set_attribute('min', min)
        }

        if (step) {
            this.set_attribute('step', step)
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
            required = false,
            disabled = false,
            readonly = false,
            hidden = false,
            autofocus = false,
            prevent_submit = false,
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
            required,
            disabled,
            readonly,
            hidden,
            autofocus,
            prevent_submit,
            max,
            min,
            step,

        })
    }
}
