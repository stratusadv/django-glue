const GlueFormFieldAttrType = {
  HTML: 'html',
  FIELD: 'field',
};


class GlueFormFieldAttr {
    // Todo: Can I remove the attr type from this in the future?
    constructor(name,  value, attr_type) {
        this.name = name
        this.value = value
        this.attr_type = attr_type
    }
}


class GlueFormField {
    constructor(
        name,
        ...field_attrs
    ) {

        // Field attrs is an array for field attr objects.
        this.set_attribute('name', name, GlueFormFieldAttrType.HTML)
        this.set_attribute('label', title_string(name), GlueFormFieldAttrType.FIELD)
        this.set_attribute('id', `id_${name}`.toLocaleLowerCase(), GlueFormFieldAttrType.HTML)

        for (const attr of field_attrs) {
            this.set_attribute(attr.name, attr.value, attr.attr_type)
        }
    }

    get label() {
        return this._label
    }

    set label(value) {
        this.set_attribute('label', value, GlueFormFieldAttrType.FIELD)
    }

    get id() {
        return this._id
    }

    set id(value) {
        this.set_attribute('id', value, GlueFormFieldAttrType.HTML)
    }

    get name() {
        return this._name
    }

    set name(value) {
        this.set_attribute('name', value, GlueFormFieldAttrType.HTML)
    }

    get required() {
        return this._required || false
    }

    set required(value) {
        if (value) {
            this.set_attribute('required', value, GlueFormFieldAttrType.HTML)
        } else {
            this.remove_attribute('required')
        }
    }

    set_attribute(name, value, attr_type) {
        this[`_${name}`] = new GlueFormFieldAttr(name, value, attr_type)
    }

    remove_attribute(name) {
        delete this[`_${name}`]
    }
}


function glue_model_field_from_field_attrs(field_attrs) {
    // Inits from glue model objects and base fields..
    let form_field = new GlueFormField(field_attrs.name.value)
    for (const [name, attr_obj] of Object.entries(field_attrs)) {
        //console.log(name)
        //console.log(attr_obj)
        form_field.set_attribute(name, attr_obj.value, attr_obj.attr_type)
    }
    return form_field
}
