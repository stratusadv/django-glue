const GlueFormFieldAttrType = {
  HTML: 'html',
  FIELD: 'field',
};


class GlueFormFieldAttr {
    constructor(name, attr_type, value) {
        this.name = name
        this.value = value
        this.attr_type = attr_type
    }
}


// has all the logic to apply to glue fields. Needs to act on an element.
class GlueFormField {
    // This should be the basic building blocks for the system.
    // A model object should be turn itself into this...
    // This just holds attributes for field objects.
    constructor(name, required = false, ...field_attrs) {
        // Todo: Need a way to initialize from model and from js....
        // Todo: Is it possible to have this render different ways? Maybe I do need a factory?
        this.name = new GlueFormFieldAttr('name', GlueFormFieldAttrType.HTML, name)
        this.id = new GlueFormFieldAttr('id', GlueFormFieldAttrType.HTML, `id_${name}`)
        this.label = new GlueFormFieldAttr('label', GlueFormFieldAttrType.FIELD, title_string(name))

        // Todo: Need to loop through these args somehow

    }

    set_required(value) {
        if (value) {
            this.required = new GlueFormFieldAttr('required', GlueFormFieldAttrType.HTML, 'required')
        } else {
            delete this.required
        }
    }

    set_attribute(name, value, attr_type) {
        this[name] = new GlueFormFieldAttr(name, attr_type, value)
    }
}


function glue_model_field_to_form_field(model_field) {
    // How would I do this for the different types of fields?
    // The binder should be the only thing that is diffreent becuase this thing just holds attributes.
    let form_field = new GlueFormField(model_field.name)
    form_field.set_attribute('label', model_field.label, GlueFormFieldAttrType.FIELD)
    form_field.set_attribute('placeholder', model_field.placeholder, GlueFormFieldAttrType.FIELD)
    return new GlueFormField()