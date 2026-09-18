import BaseGlueProxy from "./base"
import HtmlRenderer from "../htmlRenderer"

class GlueTemplateProxy extends HtmlRenderer(BaseGlueProxy) {
    async renderHtml(payload = {}) {
        const result = await this._callAttribute('render_html', payload)
        return result?.html ?? result
    }

    async _getHtml(payload = {}) {
        return this.renderHtml(payload)
    }
}

export default GlueTemplateProxy
