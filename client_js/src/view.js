import HtmlRenderer, {htmlResultFromResponse} from "./htmlRenderer"

class GlueView extends HtmlRenderer() {
    constructor(http, url, sharedPayload = {}) {
        super()
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

    async _getHtml(payload = {}) {
        return this.post(payload)
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

        return htmlResultFromResponse(response.data, globalThis.Glue).html
    }
}

export default GlueView
