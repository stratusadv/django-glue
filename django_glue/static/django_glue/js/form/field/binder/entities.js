class GlueFormFieldBinder {
    constructor(glue_form_field, field_element, label_element) {
        this.glue_form_field = glue_form_field
        this.field_element = field_element
        this.label_element = label_element
    }

    bind() {
        this.set_html_attrs()
    }

    set_html_attrs() {
        for (let field_attr of this.glue_form_field.attrs) {
            this.field_element.setAttribute(field_attr.name, field_attr.value)
        }
    }
}


class GlueCheckboxFieldBinder extends GlueFormFieldBinder {

    set_label(label_element) {
        let label = this.label_element
        this.label_element.classList.add('form-check-label')
        label.setAttribute('for', this.glue_form_field.id)
        label.innerText = this.glue_form_field.label
        this.field_element.insertAdjacentElement('afterend', label)
    }

    set_field_class() {
        this.field_element.classList.add('form-check-input')
        this.field_element.classList.add('me-2')
    }
}


class GlueSelectFieldBinder extends GlueFormFieldBinder {
    add_option(key, value) {
        const option = document.createElement('option')
        option.value = key
        option.text = value
        this.field_element.appendChild(option)
    }

    bind() {
        super.bind()
        this.field_element.innerHTML = ''
        this.add_option(null, '----------------')

        this.glue_form_field.choices.forEach(choice => {
            this.add_option(choice[0], choice[1])
        })
    }
}


class GlueRadioFieldBinder extends GlueFormFieldBinder {

    add_radio_input(key, value, index) {
        let parent_div = document.createElement('div')
        parent_div.classList.add('form-check')

        let radio_input = this.field_element.cloneNode(true)
        let increment_id = `${radio_input.id}${index}`

        radio_input.setAttribute('id', increment_id)
        radio_input.setAttribute('value', key)

        let radio_label = this.label_element.cloneNode(true)
        radio_label.setAttribute('for', increment_id)
        radio_label.innerText = value

        parent_div.appendChild(radio_input)
        parent_div.appendChild(radio_label)

        this.label_element.insertAdjacentElement('beforebegin', parent_div)
    }

    bind() {
        // Adds attributes to label and field
        super.bind()

        // Duplicates label and field and appends to area
        this.glue_form_field.choices.forEach((choice, index) => {
            this.add_radio_input(choice[0], choice[1], index)
        })

        // Hide original label and field.
        this.field_element.classList.add('d-none')
        this.label_element.classList.add('d-none')
    }

    set_label() {
        super.set_label()
        this.label_element.classList.add('mb-0')
    }

    set_field_class() {
        this.field_element.classList.add('form-check-input')
        this.field_element.classList.add('me-2')
    }

}
