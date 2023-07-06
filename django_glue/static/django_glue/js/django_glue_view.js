class GlueView {
    constructor(url) {
        this.url = url
    }


    async _render(method = 'GET', headers = {}) {
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

    render_inner(target_element) {
        this._render().then((response) => {
            return response.text()
        }).then((html) => {
            target_element.innerHTML = html
        })

    }

    render_outer(target_element) {
        this._render().then((response) => {
            return response.text()
        }).then((html) => {
            target_element.outerHTML = html
        })

    }

}
