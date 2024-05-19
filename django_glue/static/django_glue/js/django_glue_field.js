

const GlueFieldAttrType = {
  HTML: 'html',
  FIELD: 'field',
};


class GlueFieldAttr {
    constructor(name, attr_type, value) {
        this.name = name
        this.value = value
        this.attr_type = attr_type
    }
}


// has all the logic to apply to glue fields. Needs to act on an element.
class GlueField {
    constructor(field_attrs) {

        // Should this live here? Almost should be a different class and use composition?
        this._field_element = undefined
        this._label_element = undefined

        for (const [name, attr_obj] of Object.entries(field_attrs)) {
            this[name] = new GlueFieldAttr(name, attr_obj.attr_type, attr_obj.value)
        }
    }

    set_label() {
        this._label_element.setAttribute('for', this.id.value)
        this._label_element.innerText = this.label.value

        if(this.required) {
            this._label_element.innerText = this._label_element.innerText + '*'
        }
    }
    set_html_attrs() {
        // Loop though all attributes on class
        for (const [name, attr_obj] of Object.entries(this)) {
            if (attr_obj.attr_type === 'html') {
                this._field_element.setAttribute(name, attr_obj.value)
            }
        }
    }

    set_field_element(element) {
        this._field_element = element
        let previousElement = this._field_element.previousElementSibling
        if (previousElement.tagName === 'LABEL') {
            this._label_element = previousElement
            this.set_label()
        }
        this.set_html_attrs()
    }

    set_required(value) {
        if (value) {
            this.required = new GlueFieldAttr('required', GlueFieldAttrType.HTML, 'required')
        } else {
            delete this.required
        }
    }
    set_attribute(name, value, attr_type) {
        this[name] = new GlueFieldAttr(name, attr_type, value)
    }
}


class GlueSelectField extends GlueField {
    set_html_attr() {}
}
