import HtmlRenderer, {htmlResultFromResponse} from "./htmlRenderer"
import type GlueHttp from "./http"
import type {GlueViewResponse} from "./wire"

function toQueryString(data: Record<string, unknown>): URLSearchParams {
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
    http: GlueHttp
    url: string
    sharedPayload: Record<string, unknown>

    constructor(http: GlueHttp, url: string, sharedPayload: Record<string, unknown> = {}) {
        super()
        this.http = http
        const resolved = new URL(url, window.location.origin)
        this.url = `${resolved.pathname}${resolved.search}`
        this.sharedPayload = sharedPayload
    }

    async get(payload: Record<string, unknown> = {}): Promise<string | null> {
        return await this._fetchView(payload, 'GET')
    }

    async post(payload: Record<string, unknown> = {}): Promise<string | null> {
        return await this._fetchView(payload, 'POST')
    }

    async _getHtml(payload: Record<string, unknown> = {}): Promise<string | null> {
        return this.post(payload)
    }

    async _fetchView(payload: Record<string, unknown> = {}, method = 'POST'): Promise<string | null> {
        const data = {...this.sharedPayload, ...payload}
        const headers = {Accept: this.http._config.glueViewMediaType}
        let response
        if (method === 'GET') {
            const target = new URL(this.url, window.location.origin)
            toQueryString(data).forEach((value, key) => target.searchParams.append(key, value))
            response = await this.http.sendRequest<GlueViewResponse>(`${target.pathname}${target.search}`, {method: 'GET', headers})
        } else {
            response = await this.http.sendRequest<GlueViewResponse>(this.url, {
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
