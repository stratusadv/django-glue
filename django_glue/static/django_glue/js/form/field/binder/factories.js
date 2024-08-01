function glue_binder_factory(glue_form_field, field_element, label_element) {
    if (field_element.tagName === 'SELECT') {
         return new GlueSelectFieldBinder(glue_form_field, field_element, label_element)
    }
    else if (field_element.tagName === 'INPUT') {
        if (field_element.type === 'checkbox') {
            return new GlueCheckboxFieldBinder(glue_form_field, field_element, label_element)
        }
           else if (field_element.type === 'radio') {
            return new GlueRadioFieldBinder(glue_form_field, field_element, label_element)
        } else {
            return new GlueFormFieldBinder(glue_form_field, field_element, label_element)
        }
    }
    return new GlueFormFieldBinder(glue_form_field, field_element, label_element)
}
