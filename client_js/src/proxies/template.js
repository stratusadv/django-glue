import BaseGlueProxy from "./base"

class GlueTemplateProxy extends BaseGlueProxy {
    async renderHtml(payload = {}) {
        const result = await this._callAttribute('render_html', payload)
        return result?.html ?? result
    }

    async renderInnerHtml(selector, payload = {}) {
        const element = typeof selector === 'string' ? document.querySelector(selector) : selector
        const html = await this.renderHtml(payload)
        element.innerHTML = html
        return html
    }

    async renderOuterHtml(selector, payload = {}) {
        const element = typeof selector === 'string' ? document.querySelector(selector) : selector
        const html = await this.renderHtml(payload)
        element.outerHTML = html
        return html
    }

    async _renderInsertAdjacentHtml(selector, position, payload = {}) {
        const element = typeof selector === 'string' ? document.querySelector(selector) : selector
        const html = await this.renderHtml(payload)
        element.insertAdjacentHTML(position, html)
        return html
    }

    async renderInsertAdjacentHtmlBeforeBegin(selector, payload = {}) {
        return await this._renderInsertAdjacentHtml(selector, 'beforebegin', payload)
    }

    async renderInsertAdjacentHtmlAfterBegin(selector, payload = {}) {
        return await this._renderInsertAdjacentHtml(selector, 'afterbegin', payload)
    }

    async renderInsertAdjacentHtmlBeforeEnd(selector, payload = {}) {
        return await this._renderInsertAdjacentHtml(selector, 'beforeend', payload)
    }

    async renderInsertAdjacentHtmlAfterEnd(selector, payload = {}) {
        return await this._renderInsertAdjacentHtml(selector, 'afterend', payload)
    }
}

export default GlueTemplateProxy
