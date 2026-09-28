import HtmlRenderer, {htmlResultFromResponse} from "./htmlRenderer"

function toQueryString(data) {
    const params = new URLSearchParams()
    Object.entries(data).forEach(([key, value]) => {
        const values = Array.isArray(value) ? value : [value]
        values.forEach(item => params.append(
            key,
            item !== null && typeof item === 'object' ? JSON.stringify(item) : String(item),
        ))
    })
    return params
}

class GlueView extends HtmlRenderer() {
    constructor(http, url, sharedPayload = {}) {
        super()
        this.http = http
        const resolved = new URL(url, window.location.origin)
        this.url = `${resolved.pathname}${resolved.search}`
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
        const data = {...this.sharedPayload, ...payload}
        const headers = {Accept: this.http._config.glueViewMediaType}
        let response
        if (method === 'GET') {
            const target = new URL(this.url, window.location.origin)
            toQueryString(data).forEach((value, key) => target.searchParams.append(key, value))
            response = await this.http.sendRequest(`${target.pathname}${target.search}`, {method: 'GET', headers})
        } else {
            response = await this.http.sendRequest(this.url, {
                method: 'POST',
                headers,
                contentType: 'application/json',
                csrfProtected: true,
                body: JSON.stringify(data),
            })
        }

        if (response.data?.is_glue_template_response !== true) return null
        return htmlResultFromResponse(response.data, globalThis.Glue).html
    }
}

export default GlueView
