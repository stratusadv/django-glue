class GlueView {
    constructor(url, shared_parameters = {}) {
        this.url = url
        this.shared_parameters = shared_parameters
    }

    async _render(parameters = {}, method = 'POST', headers = {}) {
        const request_options = {
            method: method,
            headers: {
                ...headers,
                'X-CSRFToken': glue_get_cookie('csrftoken'),
            },
            body: JSON.stringify({...parameters, ...this.shared_parameters})
        };

        const response = await fetch(this.url, request_options);

        if (!response.ok) {
            throw new Error(`HTTP error ${response.status}`);
        }

        return response;

    }

    async render_inner(target_element, parameters = {}) {
        await this._render(parameters).then((response) => {
            return response.text()
        }).then((html) => {
            target_element.innerHTML = html
        })

    }

    async render_insert_adjacent(target_element, parameters = {}, position = 'beforeend') {
        await this._render(parameters).then((response) => {
            return response.text()
        }).then((html) => {
            target_element.insertAdjacentHTML(position, html)
        })

    }

    async render_outer(target_element, parameters = {}) {
        await this._render(parameters).then((response) => {
            return response.text()
        }).then((html) => {
            target_element.outerHTML = html
        })

    }

}
