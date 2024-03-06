class GlueFunction {
    constructor(unique_name) {
        this.unique_name = unique_name
    }

    async call(kwargs = {}) {
        let data = {
            'function': this.unique_name,
            'kwargs': kwargs,
        }

        return await glue_ajax_request(
            this.unique_name,
            'get',
            data
        ).then((response) => {
            console.log(response)
            glue_dispatch_response_event(response)
            return response.data.function_return
        })
    }

}
