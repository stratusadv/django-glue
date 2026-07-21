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
}

export default GlueTemplateProxy
