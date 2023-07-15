function glue_dispatch_response_event(response)
{
    let event = new CustomEvent('glue-response-event', {detail: response});
    window.dispatchEvent(event);
}
