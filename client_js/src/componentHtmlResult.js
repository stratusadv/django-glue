import {morphComponentRoot} from "./morph"
import {GlueProxyError} from "./errors"

// A component knows its own root, so re-rendering one takes no target. That
// removes the hand-written selector a generic HTML result requires --
// `result.renderOuterHtml('#profile-body')` -- which is the same class of
// problem as a hand-written proxy name.
class GlueComponentHtmlResult {
    constructor(html, name) {
        this.html = html
        this.name = name
    }

    toString() {
        return this.html
    }

    apply() {
        const element = document.querySelector(`[data-glue="${this.name}"]`)

        if (element === null) {
            throw new GlueProxyError(
                `Cannot apply rendered HTML for component "${this.name}": its root ` +
                `element is not in the document. It may have been removed or replaced.`
            )
        }

        morphComponentRoot(element, this.html)

        return this.html
    }
}

export default GlueComponentHtmlResult
