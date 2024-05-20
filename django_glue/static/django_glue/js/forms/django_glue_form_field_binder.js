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
        this.set_html_attrs()
    }
    set_label() {
        this._label_element.setAttribute('for', this.glue_form_field.id.value)
        this._label_element.innerText = this.glue_form_field.label.value

        if(this.glue_form_field.required) {
            this._label_element.innerText = this._label_element.innerText + '*'
        }
    }
    set_html_attrs() {
        // Loop though all attributes on class
        for (const [name, attr_obj] of Object.entries(this.glue_form_field)) {
            if (attr_obj.attr_type === 'html') {
                this._field_element.setAttribute(name, attr_obj.value)
            }
        }
    }

}