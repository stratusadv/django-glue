

class GlueFormFieldBinder {
    constructor(glue_form_field, form_field_element) {
        this.glue_form_field = glue_form_field
        this._field_element = form_field_element

    }
    bind () {
        let previousElement = this._field_element.previousElementSibling
        if (previousElement.tagName === 'LABEL') {
            this._label_element = previousElement
            this.set_label()
        }
        this.remove_ignored_attributes()
        this.set_html_attrs()
    }

    clean_attribute_name(name) {
        console.log(name)
        if (name.startsWith('_')) {
            return name.slice(1)
        } else {
            return name
        }
    }

    set_label() {
        this._label_element.setAttribute('for', this.glue_form_field.id.value)
        this._label_element.innerText = this.glue_form_field.label.value

        if(this.glue_form_field.required) {
            this._label_element.innerText = this._label_element.innerText + '*'
        }
    }
    set_html_attrs() {
        for (const [name, attr_obj] of Object.entries(this.glue_form_field)) {
            if (attr_obj.attr_type === 'html' && !this.glue_form_field.ignored_attrs.includes(name)) {
                this._field_element.setAttribute(this.clean_attribute_name(name), attr_obj.value)

            }
        }
    }

    remove_ignored_attributes() {
        // Is there an easier way to do this? I have to write special logic for the fields like label?
        for (const [name] of Object.entries(this.glue_form_field.ignored_attrs)) {
            this._field_element.removeAttribute(this.clean_attribute_name(name))
        }
    }

}