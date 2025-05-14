class ContextGlue {
    constructor(unique_name) {
        this.unique_name = encodeUniqueName(unique_name);
        window.django_glue_keep_live.add_unique_name(this.unique_name);
    }

    async get() {
        return await django_glue_ajax_request(
            this.unique_name,
            'get'
        ).then((response) => {
            django_glue_dispatch_response_event(response);
            return JSON.parse(response.data).context_data;
        }).catch((error) => {
            console.error("Error fetching context data:", error);
        });
    }
}
