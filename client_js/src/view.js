import {sendHttpRequest} from "./http";
import {updateDjangoGlueSessionData} from "./session";
import {GLUE_VIEW_URL_PATH} from "./constants";

export class ViewGlue {
    constructor(url, shared_payload = {}, skipEncodePath = true) {
        // Need to send the current view path to encode the glue data on the server.
        let config_url = new URL(window.location.origin + url)

        if (!skipEncodePath) {
            config_url.searchParams.append('glue_encode_path', window.location.pathname)
        }

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
        let viewResponse = await sendHttpRequest(GLUE_VIEW_URL_PATH, {
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

        debugger

        await window.Glue.initializeProxies(
            viewResponse.data.proxy_registry_data,
            viewResponse.data.proxy_context_data,
        )

        return viewResponse.data.html
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