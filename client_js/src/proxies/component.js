import BaseGlueProxy from "./base"
import HtmlRenderer from "../htmlRenderer"

class GlueComponentProxy extends HtmlRenderer(BaseGlueProxy) {
    get $el() {
        if (this._record.disposed || typeof document === 'undefined') return null
        return [...document.querySelectorAll('[data-glue-address]')].find(
            element => element.getAttribute('data-glue-address') === this._record.address
        ) || null
    }

    async _getHtml(payload = {}) {
        const result = await this._callAttribute('render', payload)
        return result?.html ?? result
    }
}

export default GlueComponentProxy
