function django_glue_dispatch_response_event(response) {
    let event = new CustomEvent('django-glue-response-event', {detail: response})
    window.dispatchEvent(event)
}


function django_glue_dispatch_object_delete_error_event(error) {
    let event = new CustomEvent('django-glue-object-delete-error-event', {detail: error})
    window.dispatchEvent(event)
}


function django_glue_dispatch_object_get_error_event(error) {
    let event = new CustomEvent('django-glue-object-get-error-event', {detail: error})
    window.dispatchEvent(event)
}


function django_glue_dispatch_object_method_error_event(error) {
    let event = new CustomEvent('django-glue-object-method-error-event', {detail: error})
    window.dispatchEvent(event)
}


function django_glue_dispatch_object_update_error_event(error) {
    let event = new CustomEvent('django-glue-object-update-error-event', {detail: error})
    window.dispatchEvent(event)
}
