import BaseGlueProxy from "./base"
import HtmlRenderer, {htmlToFragment} from "../htmlRenderer"
import {deliverToListeners} from "../runtime/listenerRouter"

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

    // A render keeps the children still mounted in this component (ADR 025).
    _requestFields() {
        const root = this.$el
        if (!root) return {}
        return {
            mounted: [...root.querySelectorAll('[data-glue-address]')].map(
                element => element.getAttribute('data-glue-address'),
            ),
        }
    }

    // A rendered component also dispatches its events as bubbling DOM events
    // from its root, unless the event is bubbling up from a descendant's root
    // inside this one, where the browser already carries it.
    _deliverEvent(event) {
        super._deliverEvent(event)
        const root = this.$el
        const sourceElement = event.source.$el
        if (
            root
            && typeof CustomEvent !== 'undefined'
            && !(
                this !== event.source
                && event.type === event.sourceType
                && sourceElement
                && root.contains(sourceElement)
            )
        ) {
            const domEvent = new CustomEvent(event.type, {detail: event.detail, bubbles: true})
            domEvent.source = event.source
            root.dispatchEvent(domEvent)
        }
    }

    async _applyResponse(target, result) {
        // Components reacting to this response's events re-render too, so
        // this component's own morph waits for them and the page changes once.
        await Promise.allSettled(deliverToListeners(this, target))
        // Only HTML rooted at this component's own address (its render(),
        // whether called directly or returned by an action) replaces it. Any
        // other HTML attribute on a component (a modal body, a row) is a
        // fragment for its caller to place.
        if (
            target.html !== undefined
            && this.$el
            && htmlToFragment(target.html).firstElementChild
                ?.getAttribute('data-glue-address') === this._record.address
        ) {
            await result.renderOuterHtml(this.$el)
        }
    }
}

export default GlueComponentProxy
