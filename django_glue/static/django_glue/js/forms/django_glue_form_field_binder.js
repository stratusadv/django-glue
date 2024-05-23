

class GlueFormFieldBinder {
    constructor(glue_form_field, form_field_element) {
        this.glue_form_field = glue_form_field
        this._field_element = form_field_element

    }
    bind () {
        let previous_element = this._field_element.previousElementSibling

        // Should this be simpler?
        if (previous_element.tagName === 'LABEL' && !this.glue_form_field.ignored_attrs.includes('label')) {
            this.set_label(previous_element)
        }

        this.remove_ignored_attributes()
        this.set_html_attrs()
    }

    clean_attribute_name(name) {
        if (name.startsWith('_')) {
            return name.slice(1)
        } else {
            return name
        }
    }

    set_label(label_element) {
        label_element.setAttribute('for', this.glue_form_field.id.value)
        label_element.innerText = this.glue_form_field.label.value

        if(this.glue_form_field.required && !this.glue_form_field.ignored_attrs.includes('required')) {
            label_element.innerText = label_element.innerText + '*'
        }
    }

    set_html_attrs() {
        for (const [name, attr_obj] of Object.entries(this.glue_form_field)) {
            if (attr_obj.attr_type === 'html' && !this.glue_form_field.ignored_attrs.includes(this.clean_attribute_name(name))) {
                this._field_element.setAttribute(this.clean_attribute_name(name), attr_obj.value)
            }
        }
    }

    remove_ignored_attributes() {
        for (const [index, name] of Object.entries(this.glue_form_field.ignored_attrs)) {
            this._field_element.removeAttribute(this.clean_attribute_name(name))
        }
    }

}