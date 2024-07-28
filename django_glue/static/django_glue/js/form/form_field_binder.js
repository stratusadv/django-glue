// function glue_binder_factory(glue_form_field, form_field_element) {
//     if (form_field_element.tagName === 'SELECT') {
//          return new GlueSelectFieldBinder(glue_form_field, form_field_element)
//     }
//     else if (form_field_element.tagName === 'INPUT') {
//         if (form_field_element.type === 'checkbox') {
//             return new GlueCheckboxFieldBinder(glue_form_field, form_field_element)
//         }
//            else if (form_field_element.type === 'radio') {
//             return new GlueRadioFieldBinder(glue_form_field, form_field_element)
//         } else {
//             return new GlueFormFieldBinder(glue_form_field, form_field_element)
//         }
//     }
//     return new GlueFormFieldBinder(glue_form_field, form_field_element)
// }
//
//
// class GlueFormFieldBinder {
//     constructor(form_field_element) {
//         this.glue_form_field = null
//         this._field_element = form_field_element
//     }
//
//     bind(glue_form_field) {
//         this.glue_form_field = glue_form_field
//         console.log(this.glue_form_field)
//         this.set_field_class()
//
//         if (!this.glue_form_field.ignored_attrs.includes('label')) {
//             this.set_label()
//         }
//
//         this.remove_ignored_attributes()
//         this.set_html_attrs()
//     }
//
//     clean_attribute_name(name) {
//         if (name.startsWith('_')) {
//             return name.slice(1)
//         } else {
//             return name
//         }
//     }
//
//     get label() {
//         return this._field_element.previousElementSibling
//     }
//
//     set_label() {
//         let label = this.label
//         label.classList.add('form-label')
//         label.setAttribute('for', this.glue_form_field.id)
//         label.innerText = this.glue_form_field.label
//
//         if(this.glue_form_field.required && !this.glue_form_field.ignored_attrs.includes('required')) {
//             label.innerText = label.innerText + '*'
//         }
//     }
//
//     set_field_class() {
//         this._field_element.classList.add('form-control')
//     }
//
//     set_html_attrs() {
//         for (const [name, attr_obj] of Object.entries(this.glue_form_field)) {
//             if (attr_obj.attr_type === 'html' && !this.glue_form_field.ignored_attrs.includes(this.clean_attribute_name(name))) {
//                 this._field_element.setAttribute(this.clean_attribute_name(name), attr_obj.value)
//             }
//         }
//     }
//
//     remove_ignored_attributes() {
//         for (const [index, name] of Object.entries(this.glue_form_field.ignored_attrs)) {
//             this._field_element.removeAttribute(this.clean_attribute_name(name))
//         }
//     }
// }
//
//
// class GlueCheckboxFieldBinder extends GlueFormFieldBinder {
//
//     set_label(label_element) {
//         let label = this.label
//         this.label.classList.add('form-check-label')
//         label.setAttribute('for', this.glue_form_field.id)
//         label.innerText = this.glue_form_field.label
//         this._field_element.insertAdjacentElement('afterend', label)
//     }
//
//     set_field_class() {
//         this._field_element.classList.add('form-check-input')
//         this._field_element.classList.add('me-2')
//     }
// }
//
//
// class GlueSelectFieldBinder extends GlueFormFieldBinder {
//     add_option(key, value) {
//         const option = document.createElement('option')
//         option.value = key
//         option.text = value
//         this._field_element.appendChild(option)
//     }
//
//     bind() {
//         super.bind()
//         this._field_element.innerHTML = ''
//         this.add_option(null, '----------------')
//
//         this.glue_form_field.choices.forEach(choice => {
//             this.add_option(choice[0], choice[1])
//         })
//     }
// }
//
//
// class GlueRadioFieldBinder extends GlueFormFieldBinder {
//
//     add_radio_input(key, value, index) {
//         let parent_div = document.createElement('div')
//         parent_div.classList.add('form-check')
//
//         let radio_input = this._field_element.cloneNode(true)
//         let increment_id = `${radio_input.id}${index}`
//
//         radio_input.setAttribute('id', increment_id)
//         radio_input.setAttribute('value', key)
//
//         let radio_label = this.label.cloneNode(true)
//         radio_label.setAttribute('for', increment_id)
//         radio_label.innerText = value
//
//         parent_div.appendChild(radio_input)
//         parent_div.appendChild(radio_label)
//
//         this.label.insertAdjacentElement('beforebegin', parent_div)
//     }
//
//     bind() {
//         // Adds attributes to label and field
//         super.bind()
//
//         // Duplicates label and field and appends to area
//         this.glue_form_field.choices.forEach((choice, index) => {
//             this.add_radio_input(choice[0], choice[1], index)
//         })
//
//         // Hide original label and field.
//         this._field_element.classList.add('d-none')
//         this.label.classList.add('d-none')
//     }
//
//     set_label() {
//         super.set_label()
//         this.label.classList.add('mb-0')
//     }
//
//     set_field_class() {
//         this._field_element.classList.add('form-check-input')
//         this._field_element.classList.add('me-2')
//     }
//
// }
