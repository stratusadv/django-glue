import {resolveElement, htmlToFragment} from "./utils"

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
        const element = resolveElement(target)
        const html = await this.post(payload)
        element.replaceChildren(htmlToFragment(html))
        return html
    }

    async renderOuterHtml(target, payload = {}) {
        const element = resolveElement(target)
        const html = await this.post(payload)
        element.replaceWith(htmlToFragment(html))
        return html
    }

    async _renderInsertAdjacentHtml(target, position, payload = {}) {
        const element = resolveElement(target)
        const html = await this.post(payload)
        const fragment = htmlToFragment(html)

        if (position === 'beforebegin') {
            element.before(fragment)
        } else if (position === 'afterbegin') {
            element.prepend(fragment)
        } else if (position === 'beforeend') {
            element.append(fragment)
        } else if (position === 'afterend') {
            element.after(fragment)
        } else {
            throw new Error(`Invalid insert position: ${position}`)
        }

        return html
    }

    async renderInsertAdjacentHtmlBeforeBegin(target, payload = {}) {
        return await this._renderInsertAdjacentHtml(target, 'beforebegin', payload)
    }

    async renderInsertAdjacentHtmlAfterBegin(target, payload = {}) {
        return await this._renderInsertAdjacentHtml(target, 'afterbegin', payload)
    }

    async renderInsertAdjacentHtmlBeforeEnd(target, payload = {}) {
        return await this._renderInsertAdjacentHtml(target, 'beforeend', payload)
    }

    async renderInsertAdjacentHtmlAfterEnd(target, payload = {}) {
        return await this._renderInsertAdjacentHtml(target, 'afterend', payload)
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
}

export default GlueView
