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


class GlueBaseFormField {
    static field_binder = null;
    constructor(name, id = '', label = '', required = true, help_text = '') {
        if (id === '') {
            id = name.replace(/\s/g, '_').toLowerCase();
            id = `id_${id}`;
        }

        if (label === '') {
            label = name.replace(/_/g, ' ');
            label = label.replace(/\w\S*/g, (w) => {
                return w.replace(w[0], w[0].toUpperCase());
            });
        }

        this.attrs = {};

        // Create the proxy for the attrs object
        const attrsProxy = new Proxy(this.attrs, {
            set: (target, property, value) => {
                if (property.startsWith('_')) {
                    // Direct set for internal use, bypassing proxy logic
                    target[property] = value;
                    return true;
                }
                if (!target[`_${property}`]) {
                    this.add_attribute(property, value, GlueFormFieldAttrType.HTML);
                } else {
                    target[`_${property}`].value = value;
                }
                return true;
            },
            get: (target, property) => {
                if (property.startsWith('_') && property in target) {
                    return target[property];
                } else if (`_${property}` in target) {
                    return target[`_${property}`].value;
                }
                return undefined;
            },
            ownKeys: (target) => {
                return Reflect.ownKeys(target);
            },
            getOwnPropertyDescriptor: (target, property) => {
                return Object.getOwnPropertyDescriptor(target, property) ||
                    Object.getOwnPropertyDescriptor(target, `_${property}`);
            }
        });

        // Set initial values using the proxy
        const initialValues = { name, id, label, required, help_text };
        for (const [key, value] of Object.entries(initialValues)) {
            attrsProxy[key] = value;
        }

        this.attrs = attrsProxy;
    }

    add_attribute(name, value, attr_type) {
        let glue_field_attr = new GlueFormFieldAttr(name, value, attr_type);
        this.attrs[`_${name}`] = glue_field_attr; // Directly set the underscore-prefixed property
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
        super(name, value, id, label, required, help_text);
        this.add_attribute('maxlength', max_length, GlueFormFieldAttrType.HTML);
        this.add_attribute('minlength', min_length, GlueFormFieldAttrType.HTML);
    }
}


class GlueFormField {
    constructor(
        name,
        ignored_attrs = [],
        ...field_attrs
    ) {

        this.value = ''
        this.ignored_attrs = ignored_attrs

        this.add_attribute('name', name, GlueFormFieldAttrType.HTML)
        this.add_attribute('label', title_string(name), GlueFormFieldAttrType.FIELD)
        this.add_attribute('id', `id_${name}`.toLocaleLowerCase(), GlueFormFieldAttrType.HTML)

        for (const attr of field_attrs) {
            if (attr instanceof Object) {
                this.add_attribute(attr.name, attr.value, attr.attr_type)
            }
        }

        // Return a proxy object that controls how new properties are set on the object.
        return new Proxy(this, {
            set: (target, property, value) => {
                if (!(property in target)) {
                    target.add_attribute(property, value, GlueFormFieldAttrType.HTML);
                } else {
                    target[property] = value;
                }
                return true;
            },
        });
    }

    add_attribute(name, value, attr_type) {
        // Adds name as private attribute and
        let glue_field_attr = new GlueFormFieldAttr(name, value, attr_type)

        this[`_${name}`] = glue_field_attr

        Object.defineProperty(this, glue_field_attr.name, {
        get: function() {
          return this[`_${glue_field_attr.name}`].value;
        },
        set: function(value) {
            this[`_${glue_field_attr.name}`].value = value;
            if (!value){
                this.ignore_attribute(glue_field_attr.name)
            } else {
                this.remove_ignored_attributes(glue_field_attr.name)
            }
        },
        enumerable: true,
        configurable: true
      });
    }

    allow_submit() {
        this.remove_ignored_attributes('name')
        this.remove_ignored_attributes('id')
    }

    get disabled() {
        return !!this._disabled || false
    }

    set disabled(value) {
        if (value) {
            this.add_attribute('disabled', value, GlueFormFieldAttrType.HTML)
            this.remove_ignored_attributes('disabled')
        } else {
            this.ignore_attribute('disabled')
        }
    }

    get hidden() {
        return !!this._hidden || false
    }

    set hidden(value) {
        if (value) {
            this.add_attribute('hidden', value, GlueFormFieldAttrType.HTML)
            this.ignore_attribute('label')
            this.remove_ignored_attributes('hidden')
        } else {
            this.ignore_attribute('hidden')
            this.remove_ignored_attributes('label')
        }
    }

    prevent_submit() {
        this.ignore_attribute('name')
        this.ignore_attribute('id')
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
}


function glue_model_field_from_field_attrs(field_attrs) {
    // Inits from glue model objects and base fields..
    let form_field = new GlueFormField(field_attrs.name.value)
    for (const [name, attr_obj] of Object.entries(field_attrs)) {
        form_field.add_attribute(name, attr_obj.value, attr_obj.attr_type)
    }
    return form_field
}
