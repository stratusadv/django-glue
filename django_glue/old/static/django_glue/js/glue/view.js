class ViewGlue {
    constructor(url, shared_payload = {}) {
        // Need to send the current view path to encode the glue data on the server.
        let config_url = new URL(window.location.origin + url)
        config_url.searchParams.append('glue_encode_path', window.location.pathname)

        this.url = config_url.pathname + config_url.search
        this.shared_payload = shared_payload
    }

    async get(payload = {}) {
        return await this._fetch_view(payload, 'GET')
    }

    async post(payload = {}) {
        return await this._fetch_view(payload)
    }

    async _fetch_view(payload = {}, method = 'POST') {
        let view =  await django_glue_fetch(this.url, {
            method,
            payload: {...this.shared_payload, ...payload},
            response_type: 'text',
        })
        await update_django_glue_session_data()
        return view
    }

    async render_inner(target_element, payload = {}) {
        await this._fetch_view(payload).then((response) => {
            return response
        }).then((html) => {
            target_element.innerHTML = html
        })
    }

    async render_insert_adjacent(target_element, payload = {}, position = 'beforeend') {
        await this._fetch_view(payload).then((response) => {
            return response
        }).then((html) => {
            target_element.insertAdjacentHTML(position, html)
        })
    }

    async render_outer(target_element, payload = {}) {
        await this._fetch_view(payload).then((response) => {
            return response
        }).then((html) => {
            target_element.outerHTML = html
        })
    }
}
