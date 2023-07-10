class GlueEventDispatcher extends EventTarget {
    constructor() {
        super()
        if (GlueEventDispatcher._instance) {
            return GlueEventDispatcher._instance;
        }

        GlueEventDispatcher._instance = this;
    }

    _dispatch_event(event_name = 'glue-event', detail_data = {}) {
        let event = new CustomEvent(event_name, { detail: detail_data });
        window.dispatchEvent(event);
    }

    dispatch_response_event(response) {
        this._dispatch_event('glue-response-event', response)
    }
}