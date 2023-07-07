class GlueEventDispatcher extends EventTarget {
    constructor() {
        super()
        if (GlueEventDispatcher._instance) {
            return GlueEventDispatcher._instance;
        }

        GlueEventDispatcher._instance = this;
    }

    // Todo: does custom events have to use detail as JSON value?

    _notify(event_name = 'glue_event', detail_data = {}) {
        const event = new CustomEvent(event_name, { detail: detail_data });
        this.dispatchEvent(event);
    }

    notify_response_message(detail_data) {
        this._notify('glue_response_message_event', detail_data)
    }
}