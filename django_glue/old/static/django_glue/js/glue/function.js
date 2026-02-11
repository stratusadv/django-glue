class FunctionGlue {
    constructor(unique_name) {
        this.unique_name = encodeUniqueName(unique_name)
        window.django_glue_keep_live.add_unique_name(this.unique_name)
    }

    async call(kwargs = {}) {
        let data = {
            'kwargs': kwargs,
        }

        return await django_glue_ajax_request(
            this.unique_name,
            'call',
            data
        ).then((response) => {
            django_glue_dispatch_response_event(response)
            return JSON.parse(response.data).function_return
        })
    }
}
