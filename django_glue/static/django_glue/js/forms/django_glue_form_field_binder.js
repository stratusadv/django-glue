

function glue_binder_factory(glue_form_field, form_field_element) {
    if (form_field_element.tagName === 'SELECT') {
         return new GlueSelectFieldBinder(glue_form_field, form_field_element)
    }
    else if (form_field_element.tagName === 'INPUT') {
        if (form_field_element.type === 'checkbox') {
            return new GlueCheckboxFieldBinder(glue_form_field, form_field_element)
        } else {
            return new GlueFormFieldBinder(glue_form_field, form_field_element)
        }
    }

    return new GlueFormFieldBinder(glue_form_field, form_field_element)

}

class GlueFormFieldBinder {
    constructor(glue_form_field, form_field_element) {
        this.glue_form_field = glue_form_field
        this._field_element = form_field_element
    }
    bind () {
        // Should this be simpler?
        this.set_field_class()
        if (!this.glue_form_field.ignored_attrs.includes('label')) {
            this.set_label()
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

    get label() {
        return this._field_element.previousElementSibling
    }

    set_label() {
        let label = this.label
        label.classList.add('form-label')
        label.setAttribute('for', this.glue_form_field.id)
        label.innerText = this.glue_form_field.label

        if(this.glue_form_field.required && !this.glue_form_field.ignored_attrs.includes('required')) {
            label.innerText = label.innerText + '*'
        }
    }

    set_field_class() {
        this._field_element.classList.add('form-control')
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


class GlueCheckboxFieldBinder extends GlueFormFieldBinder {
    constructor(glue_form_field, form_field_element) {
        super(glue_form_field, form_field_element)
    }

    set_label(label_element) {
        let label = this.label
        this.label.classList.add('form-check-label')
        label.setAttribute('for', this.glue_form_field.id)
        label.innerText = this.glue_form_field.label
        this._field_element.insertAdjacentElement('afterend', label);
    }

    set_field_class() {
        this._field_element.classList.add('form-check-input')
        this._field_element.classList.add('me-2')
    }
}



class GlueSelectFieldBinder extends GlueFormFieldBinder {
    constructor(glue_form_field, form_field_element) {
        super(glue_form_field, form_field_element)
    }

    add_option(key, value) {
        const option = document.createElement('option');
        option.value = key;
        option.text = value;
        this._field_element.appendChild(option);
    }

    bind() {
        super.bind()

        this._field_element.innerHTML = ''

        if (!this.glue_form_field.required) {
            this.add_option(null, '----------------')
        }

        this.glue_form_field.choices.forEach(choice => {
            this.add_option(choice[0], choice[1])

        });
    }
}


