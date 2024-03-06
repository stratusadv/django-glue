function glue_dispatch_response_event(response)
{
    let event = new CustomEvent('glue-response-event', {detail: response});
    window.dispatchEvent(event);
}

function glue_dispatch_object_delete_error_event(error)
{
    let event = new CustomEvent('glue-object-delete-error-event', {detail: error});
    window.dispatchEvent(event);
}

function glue_dispatch_object_get_error_event(error)
{
    let event = new CustomEvent('glue-object-get-error-event', {detail: error});
    window.dispatchEvent(event);
}

function glue_dispatch_object_method_error_event(error)
{
    let event = new CustomEvent('glue-object-method-error-event', {detail: error});
    window.dispatchEvent(event);
}

function glue_dispatch_object_update_error_event(error)
{
    let event = new CustomEvent('glue-object-update-error-event', {detail: error});
    window.dispatchEvent(event);
}