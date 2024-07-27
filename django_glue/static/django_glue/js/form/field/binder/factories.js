function glue_binder_factory(glue_form_field, form_field_element) {
    if (form_field_element.tagName === 'SELECT') {
         return new GlueSelectFieldBinder(glue_form_field, form_field_element)
    }
    else if (form_field_element.tagName === 'INPUT') {
        if (form_field_element.type === 'checkbox') {
            return new GlueCheckboxFieldBinder(glue_form_field, form_field_element)
        }
           else if (form_field_element.type === 'radio') {
            return new GlueRadioFieldBinder(glue_form_field, form_field_element)
        } else {
            return new GlueFormFieldBinder(glue_form_field, form_field_element)
        }
    }
    return new GlueFormFieldBinder(glue_form_field, form_field_element)
}
