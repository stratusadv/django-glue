import {sendHttpRequest} from "./http";
import {GLUE_VIEW_URL_PATH} from "./constants";

export class GlueView {
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
        return await this._fetchView(payload, 'GET')
    }

    async post(payload = {}) {
        return await this._fetchView(payload)
    }

    async #fetchView(payload = {}, method = 'POST') {
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

        window.Glue.initializeProxies(
            viewResponse.data.proxy_registry_data,
            viewResponse.data.proxy_context_data,
        )

        return viewResponse.data.html
    }

    async renderInnerHtml(target_element, payload = {}) {
        target_element.innerHTML = await this.#fetchView(payload)
    }

    async #renderInsertAdjacentHtml(target_element, position, payload = {}) {
        const html = await this.#fetchView(payload)
        target_element.insertAdjacentHTML(position, html)
    }

    async renderInsertAdjacentHtmlBeforeEnd(target_element, payload = {}) {
        await this.#renderInsertAdjacentHtml(target_element, 'beforeend', payload)
    }

    async renderInsertAdjacentHtmlAfterEnd(target_element, payload = {}) {
        await this.#renderInsertAdjacentHtml(target_element, 'afterend', payload)
    }

    async renderInsertAdjacentHtmlBeforeBegin(target_element, payload = {}) {
        await this.#renderInsertAdjacentHtml(target_element, 'beforebegin', payload)
    }

    async renderInsertAdjacentHtmlAfterBegin(target_element, payload = {}) {
        await this.#renderInsertAdjacentHtml(target_element, 'afterbegin', payload)
    }

    async renderOuterHtml(target_element, payload = {}) {
        target_element.outerHTML = await this.#fetchView(payload)
    }
}