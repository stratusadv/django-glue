const GlueFormFieldAttrType = {
  HTML: 'html',
  FIELD: 'field',
};


class GlueFormFieldAttr {
    constructor(name,  value, attr_type) {
        this.name = name
        this.value = value
        this.attr_type = attr_type
    }
}


class GlueFormField {
    constructor(
        name,
        ignored_attrs = [],
        ...field_attrs
    ) {

        // Field attrs is an array for field attr objects.
        this.value = ''
        this.ignored_attrs = ignored_attrs

        this.set_attribute('name', name, GlueFormFieldAttrType.HTML)
        this.set_attribute('label', title_string(name), GlueFormFieldAttrType.FIELD)
        this.set_attribute('id', `id_${name}`.toLocaleLowerCase(), GlueFormFieldAttrType.HTML)

        for (const attr of field_attrs) {
            this.set_attribute(attr.name, attr.value, attr.attr_type)
        }
    }

    get choices() {
        return this._choices.value || []
    }

    set choices(value) {
        this.set_attribute('choices', value, GlueFormFieldAttrType.FIELD)
    }

    get disabled() {
        return !!this._disabled || false
    }

    set disabled(value) {
        if (value) {
            this.set_attribute('disabled', value, GlueFormFieldAttrType.HTML)
            this.remove_ignored_attributes('disabled')
        } else {
            this.ignore_attribute('disabled')
        }
    }

    format_name(name) {
        return '_' + name
    }

    get help_text() {
        return this._help_text.value || ''
    }

    set help_text(value) {
        this.set_attribute('help_text', value, GlueFormFieldAttrType.FIELD)
    }

    get hidden() {
        return !!this._hidden || false
    }

    set hidden(value) {
        if (value) {
            this.set_attribute('hidden', value, GlueFormFieldAttrType.HTML)
            this.ignore_attribute('label')
            this.remove_ignored_attributes('hidden')
        } else {
            this.ignore_attribute('hidden')
            this.remove_ignored_attributes('label')
        }
    }

    get id() {
        return this._id.value
    }

    set id(value) {
        this.set_attribute('id', value, GlueFormFieldAttrType.HTML)
    }

    get label() {
        return this._label.value
    }

    set label(value) {
        this.set_attribute('label', value, GlueFormFieldAttrType.FIELD)
    }

    get name() {
        return this._name.value
    }

    set name(value) {
        this.set_attribute('name', value, GlueFormFieldAttrType.HTML)
    }

    prevent_submit() {
        this.ignore_attribute('name')
        this.ignore_attribute('id')
    }

    allow_submit() {
        this.remove_ignored_attributes('name')
        this.remove_ignored_attributes('id')
    }

    get required() {
        // console.log(this)
        return !!this._required || false
    }

    set required(value) {
        if (value) {
            this.set_attribute('required', value, GlueFormFieldAttrType.HTML)
            this.remove_ignored_attributes('required')
        } else {
            this.ignore_attribute('required')
        }
    }

    ignore_attribute(name) {
        if(!this.ignored_attrs.includes(name)) {
            this.ignored_attrs.push(name)
        }
    }

    remove_ignored_attributes(name) {
        if (this.ignored_attrs.includes(name)) {
            this.ignored_attrs.splice(this.ignored_attrs.indexOf(name), 1)
        }
    }

    set_attribute(name, value, attr_type) {
        this[this.format_name(name)] = new GlueFormFieldAttr(name, value, attr_type)
    }

}


function glue_model_field_from_field_attrs(field_attrs) {
    // Inits from glue model objects and base fields..
    let form_field = new GlueFormField(field_attrs.name.value)
    for (const [name, attr_obj] of Object.entries(field_attrs)) {
        form_field.set_attribute(name, attr_obj.value, attr_obj.attr_type)
    }
    return form_field
}
