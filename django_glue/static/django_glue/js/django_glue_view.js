class GlueView {
    constructor(url, shared_get_parameters = {}) {
        this.url = url
        this.shared_get_parameters = shared_get_parameters
    }


    // Todo: handle the get parameters
    async _render(get_parameters = {}, method = 'GET', headers = {}) {
        const request_options = {
            method: method,
            headers: {
                ...headers,
                'X-CSRFToken': glue_get_cookie('csrftoken'),
            },
        };

        const response = await fetch(this.url, request_options);

        if (!response.ok) {
            throw new Error(`HTTP error ${response.status}`);
        }

        return response;

    }

    render_inner(target_element, get_parameters = {}) {
        this._render(get_parameters).then((response) => {
            return response.text()
        }).then((html) => {
            target_element.innerHTML = html
        })

    }

    render_outer(target_element, get_parmeters = {}) {
        this._render(get_parmeters).then((response) => {
            return response.text()
        }).then((html) => {
            target_element.outerHTML = html
        })

    }

}
