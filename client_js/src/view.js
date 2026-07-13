/**
 * Server-side HTML rendering client. Sends requests to a target Django view,
 * registers any returned proxies, and injects the rendered HTML into the DOM.
 */
class GlueView {
    /**
     * @param {GlueHttp} http - The HTTP client instance.
     * @param {string} url - The target view URL path.
     * @param {Object} [shared_payload] - Payload merged into every request.
     * @param {boolean} [skipEncodePath=true] - Whether to skip appending `glue_encode_path`.
     */
    constructor(http, url, shared_payload = {}, skipEncodePath = true) {
        // Need to send the current view path to encode the glue data on the server.
        let config_url = new URL(window.location.origin + url)

        if (!skipEncodePath) {
            config_url.searchParams.append('glue_encode_path', window.location.pathname)
        }

        /** @type {GlueHttp} */
        this.http = http
        /** @type {string} */
        this.url = config_url.pathname + config_url.search
        /** @type {Object} */
        this.shared_payload = shared_payload
    }

    /**
     * Fetch rendered HTML from the target view using a GET request.
     * @param {Object} [payload] - Additional payload merged with shared_payload.
     * @returns {Promise<string>} Rendered HTML string.
     */
    async get(payload = {}) {
        return await this._fetchView(payload, 'GET')
    }

    /**
     * Fetch rendered HTML from the target view using a POST request.
     * @param {Object} [payload] - Additional payload merged with shared_payload.
     * @returns {Promise<string>} Rendered HTML string.
     */
    async post(payload = {}) {
        return await this._fetchView(payload)
    }

    /**
     * Internal fetch that sends the view request, registers returned proxies,
     * and returns the rendered HTML.
     * @param {Object} [payload] - Request payload.
     * @param {string} [method] - HTTP method ('GET' or 'POST').
     * @returns {Promise<string>} Rendered HTML string.
     * @private
     */
    async _fetchView(payload = {}, method = 'POST') {
        let viewResponse = await this.http.sendRequest(this.http._config.glueViewUrlPath, {
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

        window.Glue.init({
            proxies: viewResponse.data.proxies,
            config: this.http._config,
        })

        return viewResponse.data.html
    }

    /**
     * Parse an HTML string into DOM nodes suitable for insertion.
     * @param {string} html - The rendered HTML string.
     * @returns {DocumentFragment} Parsed DOM fragment.
     * @private
     */
    _htmlToFragment(html) {
        const template = document.createElement('template')
        template.innerHTML = html
        return template.content
    }

    /**
     * Replace the inner HTML of a target element with rendered HTML from the view.
     * @param {HTMLElement} target_element - The DOM element to update.
     * @param {Object} [payload] - Request payload.
     */
    async renderInnerHtml(target_element, payload = {}) {
        const html = await this._fetchView(payload)
        target_element.replaceChildren(this._htmlToFragment(html))
    }

    /**
     * Insert rendered HTML adjacent to a target element.
     * @param {HTMLElement} target_element - The DOM element.
     * @param {string} position - Insert position ('beforeend', 'afterend', 'beforebegin', 'afterbegin').
     * @param {Object} [payload] - Request payload.
     * @private
     */
    async _renderInsertAdjacentHtml(target_element, position, payload = {}) {
        const html = await this._fetchView(payload)
        const fragment = this._htmlToFragment(html)

        if (position === 'beforeend') {
            target_element.append(fragment)
        } else if (position === 'afterbegin') {
            target_element.prepend(fragment)
        } else if (position === 'beforebegin') {
            target_element.before(fragment)
        } else if (position === 'afterend') {
            target_element.after(fragment)
        } else {
            throw new Error(`Invalid insert position: ${position}`)
        }
    }

    /**
     * Insert rendered HTML at the end of the target element's children.
     * @param {HTMLElement} target_element - The DOM element.
     * @param {Object} [payload] - Request payload.
     */
    async renderInsertAdjacentHtmlBeforeEnd(target_element, payload = {}) {
        await this._renderInsertAdjacentHtml(target_element, 'beforeend', payload)
    }

    /**
     * Insert rendered HTML after the target element.
     * @param {HTMLElement} target_element - The DOM element.
     * @param {Object} [payload] - Request payload.
     */
    async renderInsertAdjacentHtmlAfterEnd(target_element, payload = {}) {
        await this._renderInsertAdjacentHtml(target_element, 'afterend', payload)
    }

    /**
     * Insert rendered HTML before the target element.
     * @param {HTMLElement} target_element - The DOM element.
     * @param {Object} [payload] - Request payload.
     */
    async renderInsertAdjacentHtmlBeforeBegin(target_element, payload = {}) {
        await this._renderInsertAdjacentHtml(target_element, 'beforebegin', payload)
    }

    /**
     * Insert rendered HTML at the beginning of the target element's children.
     * @param {HTMLElement} target_element - The DOM element.
     * @param {Object} [payload] - Request payload.
     */
    async renderInsertAdjacentHtmlAfterBegin(target_element, payload = {}) {
        await this._renderInsertAdjacentHtml(target_element, 'afterbegin', payload)
    }

    /**
     * Replace the target element entirely (outer HTML) with rendered HTML from the view.
     * @param {HTMLElement} target_element - The DOM element to replace.
     * @param {Object} [payload] - Request payload.
     */
    async renderOuterHtml(target_element, payload = {}) {
        const html = await this._fetchView(payload)
        target_element.replaceWith(this._htmlToFragment(html))
    }
}

export default GlueView
