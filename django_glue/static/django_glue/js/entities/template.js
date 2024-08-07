class GlueTemplate {
    constructor(unique_name, shared_context_data = {}) {
        this.unique_name = encodeUniqueName(unique_name)
        this.shared_context_data = shared_context_data
        window.glue_keep_live.add_unique_name(this.unique_name)
    }

    // Todo: Make sure there is not chance of injection attack and
    // get understanding of context data in templates
    async _render(context_data = {}) {
        let combined_context_data = Object.assign({}, this.shared_context_data, context_data);

        return await glue_ajax_request(
            this.unique_name,
            'get',
            {'context_data': combined_context_data}
        ).then((response) => {
            console.log(response)
            glue_dispatch_response_event(response)
            return response.data.rendered_template
        })
    }

    render_inner(target_element, context_data = {}) {
        this._render(context_data).then((response) => {
            glue_dispatch_response_event(response)
            return response
        }).then((html) => {
            target_element.innerHTML = html
        })
    }

    render_insert_adjacent(target_element, context_data = {}, position = 'beforeend') {
        this._render(context_data).then((response) => {
            return response
        }).then((html) => {
            target_element.insertAdjacentHTML(position, html)
        })
    }

    render_outer(target_element, context_data = {}) {
        this._render(context_data).then((response) => {
            glue_dispatch_response_event(response)
            return response
        }).then((html) => {
            target_element.outerHTML = html
        })
    }
}
