class GlueView {
    constructor(http, url, shared_payload = {}, skipEncodePath = true) {
        // Need to send the current view path to encode the glue data on the server.
        let config_url = new URL(window.location.origin + url)

        if (!skipEncodePath) {
            config_url.searchParams.append('glue_encode_path', window.location.pathname)
        }

        this.http = http
        this.url = config_url.pathname + config_url.search
        this.shared_payload = shared_payload
    }

    async get(payload = {}) {
        return await this._fetchView(payload, 'GET')
    }

    async post(payload = {}) {
        return await this._fetchView(payload)
    }

    async _fetchView(payload = {}, method = 'POST') {
        let viewResponse = await this.http.sendHttpRequest(this.http._config.glueViewUrlPath, {
            method: 'POST',
            body: JSON.stringify({
                url_path: this.url,
                method: method,
                view_payload: {
                    ...this.shared_payload,
                    ...payload
                },
            }),
            csrfProtected: true
        })

        window.Glue.initializeProxies(
            viewResponse.data.proxy_registry_data,
            viewResponse.data.proxy_context_data,
        )

        return viewResponse.data.html
    }

    async renderInnerHtml(target_element, payload = {}) {
        target_element.innerHTML = await this._fetchView(payload)
    }

    async _renderInsertAdjacentHtml(target_element, position, payload = {}) {
        const html = await this._fetchView(payload)
        target_element.insertAdjacentHTML(position, html)
    }

    async renderInsertAdjacentHtmlBeforeEnd(target_element, payload = {}) {
        await this._renderInsertAdjacentHtml(target_element, 'beforeend', payload)
    }

    async renderInsertAdjacentHtmlAfterEnd(target_element, payload = {}) {
        await this._renderInsertAdjacentHtml(target_element, 'afterend', payload)
    }

    async renderInsertAdjacentHtmlBeforeBegin(target_element, payload = {}) {
        await this._renderInsertAdjacentHtml(target_element, 'beforebegin', payload)
    }

    async renderInsertAdjacentHtmlAfterBegin(target_element, payload = {}) {
        await this._renderInsertAdjacentHtml(target_element, 'afterbegin', payload)
    }

    async renderOuterHtml(target_element, payload = {}) {
        target_element.outerHTML = await this._fetchView(payload)
    }
}

export default GlueView