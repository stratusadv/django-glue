import BaseGlueProxy from "./base"
import HtmlRenderer, {htmlToFragment} from "../htmlRenderer"
import {GlueRequestBatch} from "../http"

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

    // Calls `$receive` on every component that reacts to this response's
    // events (ADR 024, ADR 025): any mounted component that re-renders on one,
    // anywhere on the page, and any mounted ancestor with a listener for one.
    // The calls travel in one request. Returns their promises.
    _deliverEvents(target) {
        const eventIds = this._record.staticData?.event_ids || {}
        const events = (target.effects?.events || [])
            .filter(({name}) => eventIds[name])
            .map(({name, detail}) => ({
                event: eventIds[name],
                source_token: this._record.policyToken,
                detail,
            }))
        if (!events.length) return []

        const ancestors = new Set(this._record.policy.identity?.ancestors || [])
        const deliveries = [...this._registry.records.values()]
            .map(record => record.proxy)
            .filter(proxy => proxy instanceof GlueComponentProxy && proxy !== this && proxy.$el)
            .map(proxy => [proxy, proxy._reactionsTo(events, ancestors.has(proxy._record.address))])
            .filter(([, reactions]) => reactions.length)
        if (!deliveries.length) return []

        const batch = new GlueRequestBatch(this._http, deliveries.length)
        return deliveries.map(([proxy, reactions]) => (
            proxy._callAttribute('$receive', {events: reactions}, {batch})
        ))
    }

    // The events this component reacts to: those it re-renders on, and those
    // it listens for when they come from one of its descendants.
    _reactionsTo(events, fromDescendant) {
        const staticData = this._record.staticData || {}
        const reacting = new Set([
            ...(staticData.rerender_on || []),
            ...(fromDescendant ? staticData.listeners || [] : []),
        ])
        return events.filter(({event}) => reacting.has(event))
    }

    async _applyResponse(target, result) {
        // Components reacting to this response's events re-render too, so
        // this component's own morph waits for them and the page changes once.
        await Promise.allSettled(this._deliverEvents(target))
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
