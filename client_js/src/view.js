class GlueView {
    constructor(http, url, sharedPayload = {}) {
        this.http = http
        this.url = new URL(url, window.location.origin).pathname
        this.sharedPayload = sharedPayload
    }

    async get(payload = {}) {
        return await this._fetchView(payload, 'GET')
    }

    async post(payload = {}) {
        return await this._fetchView(payload, 'POST')
    }

    async renderInnerHtml(target, payload = {}) {
        const element = this._resolveElement(target)
        const html = await this.post(payload)
        element.replaceChildren(this._htmlToFragment(html))
        return html
    }

    async renderOuterHtml(target, payload = {}) {
        const element = this._resolveElement(target)
        const html = await this.post(payload)
        element.replaceWith(this._htmlToFragment(html))
        return html
    }

    async _fetchView(payload = {}, method = 'POST') {
        const response = await this.http.sendRequest(this.http._config.glueViewUrlPath, {
            method: 'POST',
            contentType: 'application/json',
            csrfProtected: true,
            body: JSON.stringify({
                url_path: this.url,
                method,
                view_payload: {
                    ...this.sharedPayload,
                    ...payload,
                },
            }),
        })

        globalThis.Glue.loadManifests(response.data?.manifest_list || [])

        return response.data?.html || ''
    }

    _resolveElement(target) {
        return typeof target === 'string' ? document.querySelector(target) : target
    }

    _htmlToFragment(html) {
        const template = document.createElement('template')
        template.innerHTML = html
        return template.content
    }
}

export default GlueView
